"""Decode Google News RSS redirect URLs into the original publisher URL.

Google News RSS items don't link straight to the article. Instead they use an
internal, encoded URL like:

    https://news.google.com/rss/articles/CBMi...AU_yqL...?oc=5

Since July 2024 the encoded token can't be decoded offline anymore. The
reliable approach is a two-step handshake with Google's undocumented
``batchexecute`` endpoint:

1. GET the article page to read a per-article ``signature`` (data-n-a-sg) and
   ``timestamp`` (data-n-a-ts).
2. POST those to ``batchexecute`` which returns the real publisher URL.

This is unofficial and may break if Google changes the format, so callers
should treat a ``None`` result as "couldn't decode" and degrade gracefully.
"""

import json
import re
from urllib.parse import quote, urlparse

import httpx

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

_BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"

_SG_RE = re.compile(r'data-n-a-sg="([^"]+)"')
_TS_RE = re.compile(r'data-n-a-ts="([^"]+)"')


def _extract_base64(source_url: str) -> str | None:
    """Return the encoded token from a Google News article/read URL."""
    parsed = urlparse(source_url)
    path = parsed.path.split("/")
    if (
        parsed.hostname == "news.google.com"
        and len(path) > 1
        and path[-2] in ("articles", "read")
    ):
        return path[-1]
    return None


async def _fetch_params(client: httpx.AsyncClient, base64_str: str) -> dict | None:
    """Fetch the signature + timestamp needed to decode the token."""
    for url in (
        f"https://news.google.com/articles/{base64_str}",
        f"https://news.google.com/rss/articles/{base64_str}",
    ):
        try:
            resp = await client.get(
                url, headers={"User-Agent": _UA}, follow_redirects=True
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            continue

        sg = _SG_RE.search(resp.text)
        ts = _TS_RE.search(resp.text)
        if sg and ts:
            return {"signature": sg.group(1), "timestamp": ts.group(1)}
    return None


async def _decode_token(
    client: httpx.AsyncClient, signature: str, timestamp: str, base64_str: str
) -> str | None:
    """Call batchexecute with the signed params to get the real URL."""
    payload = [
        "Fbv4je",
        f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,'
        f'null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
        f'"{base64_str}",{timestamp},"{signature}"]',
    ]
    resp = await client.post(
        _BATCH_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": _UA,
        },
        content=f"f.req={quote(json.dumps([[payload]]))}",
    )
    resp.raise_for_status()

    # Response is anti-JSON-hijacking prefixed; the useful part is the second
    # block, and the URL sits inside a nested JSON string.
    parsed = json.loads(resp.text.split("\n\n")[1])[:-2]
    return json.loads(parsed[0][2])[1]


async def decode_news_url(source_url: str) -> str | None:
    """Resolve a Google News redirect URL to the original publisher URL.

    Returns the original URL on success, the input unchanged if it's not a
    Google News URL, or ``None`` if decoding fails.
    """
    base64_str = _extract_base64(source_url)
    if base64_str is None:
        # Not a Google News encoded URL; assume it's already a real link.
        return source_url

    async with httpx.AsyncClient(timeout=30.0) as client:
        params = await _fetch_params(client, base64_str)
        if not params:
            return None
        try:
            return await _decode_token(
                client, params["signature"], params["timestamp"], base64_str
            )
        except (httpx.HTTPError, json.JSONDecodeError, IndexError, TypeError):
            return None
