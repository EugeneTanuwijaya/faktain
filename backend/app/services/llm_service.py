import json
import re
import asyncio
from urllib.parse import urlparse
import httpx

from app.config import settings

from app.services.provider_service import validate_llm_config, validate_vision_model, llm_headers

# Keep the existing Chat Completions abstraction and response parsing.
# Only explicitly selected OpenRouter legacy transport uses its extensions.

# Domains we consider trustworthy for credibility labeling. Sources from these
# are marked TERPERCAYA; everything else stays NETRAL.
_TRUSTED_DOMAINS = {
    "kompas.com",
    "tempo.co",
    "cnnindonesia.com",
    "bbc.com",
    "bbc.co.uk",
    "antaranews.com",
    "detik.com",
    "liputan6.com",
    "tribunnews.com",
    "kumparan.com",
    "republika.co.id",
    "suara.com",
    "katadata.co.id",
    "turnbackhoax.id",
    "cekfakta.com",
    "afp.com",
    "kominfo.go.id",
    "setkab.go.id",
}


# ---------------------------------------------------------------------------
# JSON parsing helpers (tolerant of the quirks free models emit)
# ---------------------------------------------------------------------------
def _repair_json(s: str) -> str:
    """Best-effort cleanup of common JSON defects from LLM output."""
    if not s:
        return s
    s = (
        s.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    s = re.sub(r"//[^\n\r]*", "", s)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


def _parse_json_lenient(content: str) -> dict | None:
    """Parse JSON from an LLM response, tolerating common formatting quirks."""
    if not content:
        return None

    candidates = [content]
    fenced = re.sub(r"```(?:json)?\s*", "", content).replace("```", "")
    candidates.append(fenced)
    start = fenced.find("{")
    end = fenced.rfind("}") + 1
    if start != -1 and end > start:
        candidates.append(fenced[start:end])

    for raw in candidates:
        for attempt in (raw, _repair_json(raw)):
            try:
                return json.loads(attempt)
            except (json.JSONDecodeError, TypeError):
                continue
    return None


# ---------------------------------------------------------------------------
# Source extraction from OpenRouter web-search annotations
# ---------------------------------------------------------------------------
def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _credibility(url: str) -> str:
    return "TERPERCAYA" if _domain(url) in _TRUSTED_DOMAINS else "NETRAL"


def _extract_web_sources(message: dict) -> list[dict]:
    """Pull {title, url, credibility} from OpenRouter web-search annotations.

    OpenRouter attaches cited pages under message.annotations as items of
    type "url_citation". These are the real source URLs, so no redirect
    resolution is needed.
    """
    sources: list[dict] = []
    seen: set[str] = set()
    for ann in message.get("annotations") or []:
        if ann.get("type") != "url_citation":
            continue
        cite = ann.get("url_citation", {})
        url = cite.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append(
            {
                "title": cite.get("title") or _domain(url) or url,
                "url": url,
                "credibility": _credibility(url),
            }
        )
    return sources


# ---------------------------------------------------------------------------
# OpenAI-compatible chat completion with retry + model fallback
# ---------------------------------------------------------------------------
def _build_payload(
    model: str,
    messages: list[dict],
    json_mode: bool,
    web_search: bool,
    temperature: float,
    max_tokens: int | None,
) -> dict:
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
    }
    # NOTE: forcing response_format=json_object together with the web plugin
    # makes the model skip searching (returns zero citations). So we only
    # request strict JSON mode when web search is OFF; when search is ON we
    # rely on the prompt + lenient parser to recover the JSON.
    if json_mode and not (web_search and settings.LLM_WEB_SEARCH):
        payload["response_format"] = {"type": "json_object"}
    if (web_search and settings.LLM_WEB_SEARCH and settings.LLM_PROVIDER == "openrouter"
            and settings.LLM_WEB_MODE in {"plugin", "server_tool"}):
        # OpenRouter "web" plugin. Engine is configurable (firecrawl=free but
        # needs dashboard setup; exa=$0.005/req but reliable).
        plugin: dict = {"id": "web", "max_results": settings.LLM_WEB_MAX_RESULTS}
        if settings.LLM_WEB_ENGINE:
            plugin["engine"] = settings.LLM_WEB_ENGINE
        if settings.LLM_WEB_MODE == "server_tool":
            parameters = {"max_results": settings.LLM_WEB_MAX_RESULTS,
                          "max_total_results": settings.LLM_WEB_MAX_RESULTS}
            if settings.LLM_WEB_ENGINE:
                parameters["engine"] = settings.LLM_WEB_ENGINE
            payload["tools"] = [{"type": "openrouter:web_search", "parameters": parameters}]
        else:
            payload["plugins"] = [plugin]
    return payload


def _safe_response_json(resp: httpx.Response) -> dict | None:
    """Parse a 200 response body into JSON, tolerating OpenRouter quirks.

    OpenRouter sometimes prefixes the body with keep-alive comment lines
    (": OPENROUTER PROCESSING") or returns SSE-style "data: {...}" lines even
    for non-streaming requests. A plain resp.json() then raises
    "Expecting value: line N column 1". We strip those and recover the JSON.
    """
    try:
        return resp.json()
    except Exception:
        pass

    text = resp.text or ""
    # Collect "data: {...}" payload lines (SSE-style), ignoring comments (": ..").
    data_chunks = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("data:"):
            payload = s[len("data:"):].strip()
            if payload and payload != "[DONE]":
                data_chunks.append(payload)
    for chunk in reversed(data_chunks):  # last full object is usually complete
        try:
            return json.loads(chunk)
        except Exception:
            continue

    # Last resort: slice the outermost JSON object from the raw text.
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            return None
    return None


async def _chat_completion(
    messages: list[dict],
    *,
    json_mode: bool = False,
    web_search: bool = False,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    require_json: bool = False,
    model_override: str | None = None,
    max_attempts: int | None = None,
) -> tuple[str, list[dict]]:
    """Call the configured compatible provider and return (content, web_sources).

    Retries transient 429s with backoff and falls back to alternate models.
    Empty/None content (or non-JSON when ``require_json``) is also treated as
    a retryable failure, since free models occasionally return junk.
    """
    validate_llm_config()
    if web_search and settings.LLM_WEB_SEARCH:
        if settings.LLM_WEB_MODE == "external":
            from app.services.search_service import search_messages
            return await search_messages(messages)
        if settings.LLM_PROVIDER != "openrouter":
            raise ValueError("9Router memerlukan LLM_WEB_MODE=external; plugin OpenRouter tidak kompatibel")

    has_images = any(isinstance(message.get("content"), list) and
                     any(isinstance(part, dict) and part.get("type") == "image_url"
                         for part in message["content"]) for message in messages)
    if has_images:
        if not model_override or model_override != settings.LLM_VISION_MODEL:
            raise ValueError("Input gambar memerlukan LLM_VISION_MODEL yang mendukung vision")
        await validate_vision_model(model_override)

    models = [model_override] if model_override else [settings.LLM_MODEL] + [
        m for m in settings.LLM_FALLBACK_MODELS if m != settings.LLM_MODEL
    ]
    last_error = "tidak diketahui"

    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
        for model in models:
            payload = _build_payload(
                model, messages, json_mode, web_search, temperature, max_tokens
            )

            attempts = min(settings.LLM_MAX_RETRIES, max_attempts) if max_attempts is not None else settings.LLM_MAX_RETRIES
            for attempt in range(attempts):
                try:
                    resp = await client.post(
                        f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
                        headers=llm_headers(),
                        json=payload,
                    )
                except httpx.HTTPError as e:
                    last_error = f"provider {settings.LLM_PROVIDER} tidak dapat dijangkau ({type(e).__name__})"
                    if attempt < attempts - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue

                if resp.status_code == 200:
                    data = _safe_response_json(resp)
                    if data is None:
                        # 200 but body wasn't valid JSON (e.g. OpenRouter
                        # keep-alive comment lines leaked in, or partial body).
                        last_error = "respons 200 tetapi body bukan JSON valid"
                        if attempt < attempts - 1:
                            await asyncio.sleep(1)
                        continue
                    try:
                        message = data["choices"][0]["message"]
                        content = message.get("content")
                        if require_json and data["choices"][0].get("finish_reason") not in (None, "stop"):
                            content = None
                    except (KeyError, IndexError, TypeError, AttributeError):
                        message, content = {}, None

                    if not isinstance(content, str) or not content or (
                        require_json and _parse_json_lenient(content) is None
                    ):
                        last_error = (
                            f"model '{model}' mengembalikan respons kosong/non-JSON"
                        )
                        if attempt < attempts - 1:
                            await asyncio.sleep(1)
                        continue

                    return content, _extract_web_sources(message)

                try:
                    body = resp.json()
                    err = body.get("error", {}).get("message", resp.text)
                except Exception:
                    err = resp.text
                last_error = f"{resp.status_code}: {err}"

                # Non-429 errors (404 model removed, 400, 5xx) won't heal by
                # retrying the SAME model — move on to the next fallback
                # instead of aborting the whole chain.
                if resp.status_code != 429:
                    break

                retry_after = resp.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else 2 ** attempt
                except ValueError:
                    delay = 2 ** attempt
                if attempt < attempts - 1:
                    await asyncio.sleep(min(delay, 15))

    raise ValueError(
        f"LLM API error {last_error}. Semua model (termasuk fallback) gagal "
        f"memberi respons valid. Coba lagi sebentar lagi."
    )


def _normalize_claim_status(status: str) -> str:
    """Map model status variants to the canonical set.

    Free models emit variants like "BELUM TERVERIFIKASI", "TIDAK TERVERIFIKASI",
    or English equivalents. Collapse them into the three statuses the UI knows:
    TERKONFIRMASI | DIBANTAH | TIDAK DAPAT DIVERIFIKASI.
    """
    s = str(status or "").strip().upper()
    if not s:
        return "TIDAK DAPAT DIVERIFIKASI"
    # Debunked / false
    if any(k in s for k in ("DIBANTAH", "SALAH", "HOAKS", "HOAX", "FALSE", "KELIRU")):
        return "DIBANTAH"
    # Confirmed / true
    if any(k in s for k in ("TERKONFIRMASI", "KONFIRM", "BENAR", "TRUE", "CONFIRMED", "VALID")):
        return "TERKONFIRMASI"
    # Everything else (BELUM TERVERIFIKASI, TIDAK DAPAT DIVERIFIKASI, UNVERIFIED, ...)
    return "TIDAK DAPAT DIVERIFIKASI"


def _enforce_verdict_consistency(result: dict) -> None:
    """Keep verdict and confidence_score consistent.

    confidence_score is a CREDIBILITY score (0=hoax, 100=credible). Smaller
    models sometimes emit a verdict that contradicts the score (e.g. verdict
    KEMUNGKINAN HOAKS with score 95) or claims that contradict the verdict.
    We first normalize claim statuses, then fix the verdict against the CORE
    claims only (peripheral context must not drag down the score), then clamp
    the score into the band that matches the final verdict.
    """
    claims = result.get("verified_claims") or []

    # --- Normalize statuses + default is_core so the UI/logic see clean data ---
    for c in claims:
        if isinstance(c, dict):
            c["status"] = _normalize_claim_status(c.get("status", ""))
            if "is_core" not in c or not isinstance(c.get("is_core"), bool):
                c["is_core"] = True

    # Only CORE claims (those the user actually stated) drive the verdict.
    # If the model marked everything peripheral, fall back to all claims so we
    # don't lose signal entirely.
    core = [c for c in claims if isinstance(c, dict) and c.get("is_core")]
    judging = core or [c for c in claims if isinstance(c, dict)]
    statuses = [str(c.get("status", "")).upper() for c in judging]
    verdict = str(result.get("verdict", "")).upper()
    reasoning = str(result.get("reasoning", "")).lower()

    # --- DETECT HALLUCINATION: model claims "no web access" despite grounding ---
    # This is a critical bug where the model ignores the web search brief and
    # claims it cannot verify. When this happens, downgrade to PERLU DICEK but
    # flag the issue in reasoning.
    hallucination_phrases = [
        "tidak memiliki akses",
        "tidak dapat mengakses internet",
        "tidak ada akses web",
        "saya tidak dapat memverifikasi klaim ini karena tidak",
    ]
    if any(phrase in reasoning for phrase in hallucination_phrases):
        # Model ignored the web brief. Keep verdict conservative (PERLU DICEK)
        # but inject a note so we can diagnose this pattern.
        result["_hallucination_detected"] = True
        if verdict not in ["PERLU DICEK", "KEMUNGKINAN HOAKS"]:
            verdict = "PERLU DICEK"

    has_debunked = any("DIBANTAH" in s for s in statuses)
    all_confirmed = bool(statuses) and all("TERKONFIRMASI" in s for s in statuses)
    any_confirmed = any("TERKONFIRMASI" in s for s in statuses)

    # --- Step 1: reconcile the verdict with the CORE claim evidence ---
    # A debunked core claim always knocks the verdict down. But an unverifiable
    # core claim only downgrades KREDIBEL when NONE of the core claims are
    # confirmed — a fully-confirmed core set should stay KREDIBEL even if a
    # peripheral detail was unverifiable.
    if has_debunked and verdict == "KREDIBEL":
        verdict = "KEMUNGKINAN HOAKS"
    elif verdict == "KREDIBEL" and judging and not all_confirmed and not any_confirmed:
        verdict = "PERLU DICEK"
    result["verdict"] = verdict

    # --- Step 2: clamp the credibility score into the verdict's band ---
    # KEMUNGKINAN HOAKS -> 0-30, PERLU DICEK -> 40-60, KREDIBEL -> 75-100.
    bands = {
        "KEMUNGKINAN HOAKS": (0, 30),
        "PERLU DICEK": (40, 60),
        "KREDIBEL": (75, 100),
    }
    band = bands.get(verdict)
    if band is None:
        return
    low, high = band
    score = result.get("confidence_score")
    if not isinstance(score, (int, float)):
        # Missing/invalid score -> use the middle of the band.
        result["confidence_score"] = (low + high) // 2
        return
    # Pull an out-of-band score to the nearest edge of its verdict's band.
    result["confidence_score"] = int(max(low, min(high, score)))


# ---------------------------------------------------------------------------
# News summarization (no web search needed; summarize the scraped article)
# ---------------------------------------------------------------------------
async def summarize_article(title: str, content: str, *, timeout: float | None = None) -> str:
    """Summarize the scraped original article through the dedicated Langflow flow."""
    from app.services.langflow_service import summarize_with_langflow
    return await summarize_with_langflow(title, content, timeout=timeout)
