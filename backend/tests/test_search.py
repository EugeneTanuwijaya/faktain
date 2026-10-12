"""DuckDuckGo HTML is discovery data, never final article evidence."""
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx
import pytest

from app.config import settings
from app.services import search_service
from app.services.search_service import search_messages, validate_search_config


@pytest.fixture(autouse=True)
def search_config(monkeypatch):
    monkeypatch.setattr(search_service, "_blocked_until", 0.0, raising=False)
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(settings, "LLM_WEB_SEARCH", True)
    monkeypatch.setattr(settings, "LLM_WEB_MODE", "external")
    monkeypatch.setattr(settings, "LLM_WEB_MAX_RESULTS", 2)


async def run(response):
    original = httpx.AsyncClient
    def handler(request):
        assert request.url.host == "html.duckduckgo.com"
        assert request.method == "POST"
        assert parse_qs(request.content.decode())["q"] == ["klaim"]
        assert "authorization" not in request.headers and "x-api-key" not in request.headers
        return response
    with patch("httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
        return await search_messages([{"role": "user", "content": "klaim"}])


@pytest.mark.asyncio
async def test_redirect_unwrap_dedup_invalid_urls_and_result_limit():
    links = ["//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa", "https://example.com/a",
             "javascript:alert(1)", "https://user:password@example.com/", "https://example.com:9000/",
             "https://example.org/b", "https://example.net/c"]
    html = "".join(f'<div class="result"><a class="result__a" href="{url}">Artikel</a></div>' for url in links)
    _, sources = await run(httpx.Response(200, text=html))
    assert [s["url"] for s in sources] == ["https://example.com/a", "https://example.org/b"]


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [httpx.Response(202), httpx.Response(429),
    httpx.Response(200, text='<form id="challenge-form">CAPTCHA</form>'),
    httpx.Response(200, text="<html>Unexpected layout</html>"),
    httpx.Response(200, content=b"x" * (1_048_576 + 1))])
async def test_blocked_malformed_or_oversized_response_is_service_failure(response):
    with pytest.raises(ValueError, match="Search duckduckgo gagal"):
        await run(response)


@pytest.mark.asyncio
async def test_genuine_no_results_is_not_service_failure():
    assert await run(httpx.Response(200, text='<div class="no-results">No results found</div>')) == ("", [])


def test_unsupported_provider_and_result_budget_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "exa")
    with pytest.raises(ValueError, match="duckduckgo"):
        validate_search_config()
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(settings, "LLM_WEB_MAX_RESULTS", 6)
    with pytest.raises(ValueError, match="1 dan 5"):
        validate_search_config()


@pytest.mark.asyncio
async def test_network_error_is_sanitized_and_not_retried():
    original = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("private-payload", request=request)
    with patch("httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
        with pytest.raises(ValueError, match="ConnectError") as error:
            await search_messages([{"role": "user", "content": "klaim"}])
    assert "private-payload" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body,expected_wait", [(429, "", 120), (202, "challenge", 300),
    (200, '<form id="challenge-form">CAPTCHA</form>', 300)])
async def test_blocked_search_waits_and_does_not_repeat_network_calls(status, body, expected_wait):
    original = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=body, headers={"Retry-After": "120"})
    with patch("httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
        for _ in range(2):
            with pytest.raises(ValueError) as error:
                await search_messages([{"role": "user", "content": "klaim"}])
            assert error.value.retry_after == expected_wait
    assert len(calls) == 1


def test_retry_after_http_date_invalid_and_bounded_values(monkeypatch):
    monkeypatch.setattr(search_service.time, "time", lambda: 0)
    assert search_service._retry_after("Thu, 01 Jan 1970 00:02:00 GMT") == 120
    assert search_service._retry_after("not-a-date") == 60
    assert search_service._retry_after("999999999") == 86400


@pytest.mark.asyncio
async def test_search_resumes_after_cooldown_expires(monkeypatch):
    original = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429) if len(calls) == 1 else httpx.Response(200, text='<div class="no-results">No results found</div>')
    with patch("httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
        with pytest.raises(search_service.SearchBlocked):
            await search_messages([{"role": "user", "content": "klaim"}])
        monkeypatch.setattr(search_service, "_blocked_until", search_service.time.monotonic() - 1)
        assert await search_messages([{"role": "user", "content": "klaim"}]) == ("", [])
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_doh_pins_public_ip_preserves_host_tls_and_form_query(monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_DNS_OVER_HTTPS", True, raising=False)
    original = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.host == "1.1.1.1":
            assert request.url.params["name"] == "html.duckduckgo.com"
            assert "q" not in request.url.params
            return httpx.Response(200, json={"Status": 0, "Answer": [{"type": 5, "data": "duckduckgo.com."}, {"type": 1, "data": "20.43.161.105"}]})
        assert request.url.host == "20.43.161.105"
        assert request.headers["host"] == "html.duckduckgo.com"
        assert request.extensions["sni_hostname"] == "html.duckduckgo.com"
        assert request.method == "POST" and parse_qs(request.content.decode())["q"] == ["klaim"]
        return httpx.Response(200, text='<div class="result"><a class="result__a" href="https://example.com/a">Artikel</a></div>')
    with patch("httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
        _, sources = await search_messages([{"role": "user", "content": "klaim"}])
    assert len(calls) == 2 and len(sources) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"Status": 3}, {"Status": 0, "Answer": [{"type": 1, "data": "127.0.0.1"}]},
    {"Status": 0, "Answer": [{"type": 1, "data": "10.0.0.1"}]},
    {"Status": 0, "Answer": [{"type": 1, "data": "not-an-ip"}]}, {"Status": 0, "Answer": "bad"}])
async def test_doh_invalid_or_nonpublic_response_cannot_start_search(monkeypatch, payload):
    monkeypatch.setattr(settings, "SEARCH_DNS_OVER_HTTPS", True, raising=False)
    original = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == "1.1.1.1"
        return httpx.Response(200, json=payload)
    with patch("httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
        with pytest.raises(ValueError, match="DNS"):
            await search_messages([{"role": "user", "content": "klaim"}])
    assert len(calls) == 1
