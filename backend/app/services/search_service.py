"""DuckDuckGo discovers URLs; only safely fetched articles become evidence."""
import asyncio
import ipaddress
import json
import math
import time
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.config import settings

_blocked_until = 0.0
_blocked_reason = ""


class SearchBlocked(ValueError):
    def __init__(self, reason: str, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Search duckduckgo gagal: {reason}; pencarian dihentikan sementara. Coba kembali setelah {retry_after} detik.")


def _block(reason: str, seconds: int) -> SearchBlocked:
    global _blocked_until, _blocked_reason
    _blocked_until = max(_blocked_until, time.monotonic() + seconds)
    _blocked_reason = reason
    return SearchBlocked(reason, math.ceil(_blocked_until - time.monotonic()))


def _retry_after(value: str) -> int:
    try:
        seconds = int(value) if value.isdecimal() else math.ceil(parsedate_to_datetime(value).timestamp() - time.time())
    except (ValueError, TypeError, OverflowError):
        seconds = 60
    return min(86400, max(1, seconds))


async def _read_limited(response: httpx.Response, limit: int) -> bytes:
    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > limit:
            raise ValueError("respons melebihi batas ukuran")
        body.extend(chunk)
    return bytes(body)


def validate_search_config() -> None:
    if not settings.LLM_WEB_SEARCH:
        return
    if settings.LLM_WEB_MODE in {"plugin", "server_tool"} and settings.LLM_PROVIDER == "openrouter":
        return  # Audited legacy transport, never sent to 9Router.
    if settings.LLM_WEB_MODE != "external":
        raise ValueError("LLM_WEB_MODE=external diperlukan untuk provider selain OpenRouter")
    if settings.SEARCH_PROVIDER != "duckduckgo":
        raise ValueError("SEARCH_PROVIDER tidak didukung; gunakan duckduckgo")
    if not 1 <= settings.LLM_WEB_MAX_RESULTS <= 5:
        raise ValueError("LLM_WEB_MAX_RESULTS harus antara 1 dan 5")


async def search_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    validate_search_config()
    # Search claims as data, never execute model-selected tools or instructions.
    query = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query pencarian kosong/tidak valid")
    try:
        envelope = json.loads(query)
        if isinstance(envelope, dict) and isinstance(envelope.get("claim"), str):
            query = envelope["claim"]
            reference = envelope.get("today")
            visual = envelope.get("visual_observation")
            if isinstance(reference, str) and reference.strip():
                query += f"\nTanggal referensi untuk waktu relatif (bukan tanggal kejadian klaim): {reference[:40]}"
            if isinstance(visual, str) and visual.strip():
                query += f"\nKonteks visual untuk mencari gambar sumber (observasi, bukan bukti): {visual[:1000]}"
    except ValueError:
        pass
    # shortcut: public HTML can change or be rate-limited; upgrade to a supported API if reliability is required.
    try:
        if time.monotonic() < _blocked_until:
            raise SearchBlocked(_blocked_reason, math.ceil(_blocked_until - time.monotonic()))
        async with asyncio.timeout(15.0), httpx.AsyncClient(timeout=15.0, trust_env=False, follow_redirects=False) as client:
            target = "https://html.duckduckgo.com/html/"
            headers = {"User-Agent": "Faktain/1.0"}
            extensions = {}
            if settings.SEARCH_DNS_OVER_HTTPS:
                # Resolve only the fixed search host; never model-selected or article URLs.
                async with client.stream("GET", "https://1.1.1.1/dns-query",
                                         params={"name": "html.duckduckgo.com", "type": "A"},
                                         headers={"Accept": "application/dns-json"}) as dns_response:
                    if dns_response.status_code != 200:
                        raise ValueError("DNS HTTPS tidak tersedia")
                    try:
                        dns = json.loads(await _read_limited(dns_response, 16_384))
                        if not isinstance(dns, dict) or dns.get("Status") != 0 or not isinstance(dns.get("Answer"), list):
                            raise ValueError()
                        addresses = [ipaddress.ip_address(a["data"]) for a in dns["Answer"]
                                     if isinstance(a, dict) and a.get("type") == 1]
                        if not addresses or any(a.version != 4 or not a.is_global for a in addresses):
                            raise ValueError()
                    except (ValueError, KeyError, TypeError):
                        raise ValueError("Respons DNS HTTPS tidak valid") from None
                target = f"https://{addresses[0]}/html/"
                headers["Host"] = "html.duckduckgo.com"
                extensions["sni_hostname"] = "html.duckduckgo.com"
            async with client.stream("POST", target,
                                     data={"q": query[:2000], "kl": "id-id", "kp": "1"},
                                     headers=headers, extensions=extensions) as response:
                if response.status_code == 429:
                    raise _block("HTTP 429 / rate limit DuckDuckGo", _retry_after(response.headers.get("Retry-After", "")))
                if response.status_code in {202, 403}:
                    raise _block(f"HTTP {response.status_code} / akses DuckDuckGo dibatasi", 300)
                if response.status_code != 200:
                    raise ValueError(f"HTTP {response.status_code}")
                body = await _read_limited(response, 1_048_576)
        html = BeautifulSoup(body.decode("utf-8", errors="replace"), "html.parser")
        if html.select_one("#challenge-form, #anomaly-form, .anomaly-modal"):
            raise _block("CAPTCHA/challenge DuckDuckGo", 300)
        links = html.select(".result__a")
        if not links:
            if html.select_one(".no-results"):
                return "", []
            raise ValueError("format hasil pencarian tidak dikenali")
        from app.services.llm_service import _credibility
        sources, briefs, seen = [], [], set()
        for link in links:
            href = link.get("href")
            if not isinstance(href, str) or not href.strip():
                continue
            try:
                url = urljoin("https://html.duckduckgo.com/", href)
                parsed = urlsplit(url)
                if parsed.hostname in {"duckduckgo.com", "html.duckduckgo.com"} and parsed.path == "/l/":
                    url = parse_qs(parsed.query).get("uddg", [""])[0]
                parsed = urlsplit(url)
                if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                        or parsed.username is not None or parsed.password is not None
                        or parsed.port not in {None, 80, 443} or url in seen):
                    continue
            except ValueError:
                continue
            seen.add(url)
            title = link.get_text(" ", strip=True) or parsed.hostname
            sources.append({"title": title, "url": url, "credibility": _credibility(url)})
            result = link.find_parent(class_="result")
            snippet = result.select_one(".result__snippet") if result else None
            text = snippet.get_text(" ", strip=True)[:2000] if snippet else ""
            briefs.append(f"{title}: {text} ({url})")
            if len(sources) >= settings.LLM_WEB_MAX_RESULTS:
                break
        return "\n".join(briefs), sources
    except SearchBlocked:
        raise
    except httpx.HTTPError as exc:
        reason = type(exc).__name__
    except TimeoutError:
        reason = "deadline pencarian habis"
    except ValueError as exc:
        reason = str(exc)
    raise ValueError(f"Search duckduckgo gagal: {reason}; evidence tidak boleh diganti dengan ingatan model")
