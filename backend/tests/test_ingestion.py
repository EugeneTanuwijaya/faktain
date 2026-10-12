import base64
import io
import socket
import gzip
import tracemalloc
from unittest.mock import patch

import pytest
from PIL import Image
from pydantic import ValidationError

from app.models.request_models import AnalyzeRequest
from app.services.image_service import normalize_image
from app.services.url_safety import public_target
from app.services.url_safety import safe_fetch
import httpx


def image_url(data=None):
    if data is None:
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
        data = buffer.getvalue()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def test_image_is_decoded_and_normalized():
    normalized = normalize_image(image_url())
    assert normalized.startswith("data:image/jpeg;base64,")
    with Image.open(io.BytesIO(base64.b64decode(normalized.split(",")[1]))) as img:
        assert img.size == (10, 10)


@pytest.mark.parametrize("value", [image_url(b"not a picture"), "data:image/png;base64,???",
                                  "data:image/svg+xml;base64,PHN2Zz4=", "https://example.com/a.png"])
def test_invalid_image_rejected(value):
    with pytest.raises(ValueError):
        normalize_image(value)


def test_image_size_bounded_before_decode():
    with pytest.raises(ValueError, match="5 MiB"):
        normalize_image("data:image/png;base64," + "A" * 7_000_000)


def test_input_requires_one_primary_modality_but_allows_image_caption():
    AnalyzeRequest(text="caption", image_data_url=image_url())
    AnalyzeRequest(text="Ini teks berita untuk dianalisis")
    for values in ({}, {"text": "abc", "url": "https://example.com"},
                   {"url": "https://example.com", "image_data_url": image_url()}):
        with pytest.raises(ValidationError):
            AnalyzeRequest(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1", "http://169.254.169.254",
                                 "http://[::1]", "https://user:password@example.com", "https://example.com:22"])
async def test_private_or_non_http_targets_rejected(url):
    with pytest.raises(ValueError):
        await public_target(url)


@pytest.mark.asyncio
async def test_public_hostname_resolving_private_ip_is_rejected():
    with patch("app.services.url_safety.socket.getaddrinfo", return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))
    ]):
        with pytest.raises(ValueError):
            await public_target("https://attacker.example/article")


@pytest.mark.asyncio
async def test_private_redirect_is_revalidated_before_second_request():
    original = httpx.AsyncClient
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("app.services.url_safety.socket.getaddrinfo", return_value=public_dns), \
         patch("app.services.url_safety.httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
        with pytest.raises(ValueError, match="publik"):
            await safe_fetch("https://example.com/article")
    assert len(requests) == 1
    assert requests[0].url.host == "93.184.216.34"
    assert requests[0].headers["host"] == "example.com"
    assert requests[0].extensions["sni_hostname"] == "example.com"


@pytest.mark.asyncio
async def test_source_download_is_bounded():
    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/html"}, stream=httpx.ByteStream(b"x" * 101)))
    with patch("app.services.url_safety.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]), \
         patch("app.services.url_safety.httpx.AsyncClient", lambda **kw: original(transport=transport, **kw)):
        with pytest.raises(ValueError, match="terlalu besar"):
            await safe_fetch("https://example.com/article", max_bytes=100)


@pytest.mark.asyncio
async def test_compressed_response_cannot_expand_beyond_download_limit():
    compressed = gzip.compress(b"x" * (16 * 1024 * 1024))
    class EncodedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield compressed

    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200,
        headers={"content-type": "text/html", "content-encoding": "gzip"}, stream=EncodedStream()))
    with patch("app.services.url_safety.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]), \
         patch("app.services.url_safety.httpx.AsyncClient", lambda **kw: original(transport=transport, **kw)):
        tracemalloc.start()
        try:
            with pytest.raises(ValueError, match="terlalu besar"):
                await safe_fetch("https://example.com/article", max_bytes=100_000)
            _, peak = tracemalloc.get_traced_memory()
            assert peak < 5 * 1024 * 1024
        finally:
            tracemalloc.stop()


@pytest.mark.asyncio
async def test_regular_gzip_article_is_decoded_within_limit():
    body = b"<html>article content</html>"
    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200,
        headers={"content-type": "text/html", "content-encoding": "gzip"}, stream=httpx.ByteStream(gzip.compress(body))))
    with patch("app.services.url_safety.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]), \
         patch("app.services.url_safety.httpx.AsyncClient", lambda **kw: original(transport=transport, **kw)):
        content, _, _ = await safe_fetch("https://example.com/article", max_bytes=100)
    assert content == body


@pytest.mark.asyncio
@pytest.mark.parametrize("separate_chunk", [True, False])
async def test_gzip_tail_bytes_are_rejected_not_accumulated(separate_chunk):
    compressed = gzip.compress(b"<html>valid source text</html>")
    class TailedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            if separate_chunk:
                yield compressed
                yield b"junk" * 20
            else:
                yield compressed + b"junk"
    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200,
        headers={"content-type": "text/html", "content-encoding": "gzip"}, stream=TailedStream()))
    with patch("app.services.url_safety.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]), \
         patch("app.services.url_safety.httpx.AsyncClient", lambda **kw: original(transport=transport, **kw)):
        with pytest.raises(ValueError):
            await safe_fetch("https://example.com/article", max_bytes=100)
