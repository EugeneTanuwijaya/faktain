"""Provider transport contracts; network calls use HTTP fixtures, never live keys."""
import json
from urllib.parse import parse_qs
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import llm_service


@pytest.fixture(autouse=True)
def provider_config(monkeypatch):
    for name, value in {
        "LLM_PROVIDER": "9router", "LLM_BASE_URL": "http://localhost:20128/v1",
        "LLM_API_KEY": "local-key", "LLM_MODEL": "test/text",
        "LLM_VISION_MODEL": "test/vision", "LLM_VISION_MODELS": [],
        "LLM_FALLBACK_MODELS": [], "LLM_MAX_RETRIES": 2,
        "SEARCH_PROVIDER": "duckduckgo",
    }.items():
        monkeypatch.setattr(settings, name, value, raising=False)


def mock_http(handler):
    original = httpx.AsyncClient
    return patch("httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def catalog(vision=True):
    return {"data": [{"id": "test/text"}, {"id": "test/vision", "capabilities": {"vision": vision}}]}


@pytest.mark.asyncio
async def test_chat_uses_current_generic_config_and_no_provider_extensions():
    def handler(request):
        assert str(request.url) == "http://localhost:20128/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer local-key"
        assert "HTTP-Referer" not in request.headers
        payload = json.loads(request.content)
        assert payload["model"] == "test/text"
        assert payload["response_format"] == {"type": "json_object"}
        assert "tools" not in payload and "plugins" not in payload
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"claims": []}'}}]})
    with mock_http(handler):
        content, sources = await llm_service._chat_completion([{"role": "user", "content": "test"}], json_mode=True)
    assert json.loads(content) == {"claims": []} and sources == []


@pytest.mark.asyncio
async def test_external_search_keeps_real_citations_without_calling_llm():
    def handler(request):
        assert request.url.host == "html.duckduckgo.com"
        assert request.method == "POST"
        assert "x-api-key" not in request.headers
        assert "authorization" not in request.headers
        query = parse_qs(request.content.decode())["q"][0]
        assert query.startswith("Indonesia merdeka 1945")
        assert "2026-10-09" in query
        return httpx.Response(200, text='''<div class="result"><a class="result__a" href="https://kompas.com/archive">Arsip</a><div class="result__snippet">Arsip asli</div></div><div class="result"><a class="result__a" href="https://kompas.com/archive">Duplicate</a></div><div class="result"><a class="result__a" href="javascript:bad">Bad</a></div>''')
    with mock_http(handler):
        brief, sources = await llm_service._chat_completion(
            [{"role": "user", "content": json.dumps({"claim": "Indonesia merdeka 1945", "today": "2026-10-09"})}], web_search=True)
    assert [s["url"] for s in sources] == ["https://kompas.com/archive"]
    assert sources[0]["credibility"] == "TERPERCAYA"
    assert "Arsip asli" in brief


@pytest.mark.asyncio
@pytest.mark.parametrize("vision", [False, None])
async def test_image_rejects_text_only_or_unconfirmed_model_before_chat(vision):
    def handler(request):
        assert request.url.path == "/v1/models"
        data = catalog(vision)
        if vision is None:
            data["data"][1].pop("capabilities")
        return httpx.Response(200, json=data)
    with mock_http(handler), pytest.raises(ValueError, match="vision"):
        await llm_service._chat_completion(
            [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,test"}}]}],
            model_override="test/vision")


@pytest.mark.asyncio
async def test_vision_keeps_image_payload_and_never_uses_text_fallback(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACK_MODELS", ["test/text"])
    messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,test"}}]}]
    calls = []
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=catalog())
        payload = json.loads(request.content)
        calls.append(payload)
        return httpx.Response(400, json={"error": {"message": "vision unavailable"}})
    with mock_http(handler), pytest.raises(ValueError):
        await llm_service._chat_completion(messages, model_override="test/vision")
    assert len(calls) == 1
    assert calls[0]["model"] == "test/vision" and calls[0]["messages"] == messages


@pytest.mark.asyncio
async def test_models_health_and_startup_validate_reachability():
    with mock_http(lambda request: httpx.Response(200, json=catalog())):
        with TestClient(app) as client:
            response = client.get("/health/llm")
    assert response.status_code == 200
    assert response.json()["provider"] == "9router"


@pytest.mark.parametrize("field", ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"])
def test_startup_rejects_missing_required_config(monkeypatch, field):
    monkeypatch.setattr(settings, field, "")
    with pytest.raises(ValueError, match=field):
        with TestClient(app):
            pass


def test_startup_rejects_unreachable_provider():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)
    with mock_http(handler), pytest.raises(ValueError, match="9router.*tidak dapat dijangkau"):
        with TestClient(app):
            pass


@pytest.mark.asyncio
async def test_provider_outage_health_is_clear_and_does_not_leak_key():
    with mock_http(lambda request: httpx.Response(401, text="local-key")):
        response = TestClient(app).get("/health/llm")
    assert response.status_code == 503
    assert "401" in response.json()["detail"]
    assert "local-key" not in response.text


@pytest.mark.asyncio
async def test_rate_limit_retry_still_succeeds(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 2)
    attempts = []
    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
    with mock_http(handler):
        content, _ = await llm_service._chat_completion([{"role": "user", "content": "ping"}])
    assert content == "OK" and len(attempts) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", [
    {"id": "test/vision", "architecture": {"input_modalities": ["text", "image"]}},
    {"id": "test/vision"},
])
async def test_vision_catalog_or_confirmed_allowlist_accepts_images(monkeypatch, entry):
    monkeypatch.setattr(settings, "LLM_VISION_MODELS", ["test/vision"])
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [entry]})
        assert json.loads(request.content)["model"] == "test/vision"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ocr_text":"teks"}'}}]})
    with mock_http(handler):
        content, _ = await llm_service._chat_completion(
            [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,test"}}]}],
            model_override="test/vision", json_mode=True)
    assert json.loads(content)["ocr_text"] == "teks"


def test_allowlist_cannot_override_explicit_text_only_metadata(monkeypatch):
    from app.services.provider_service import check_vision
    monkeypatch.setattr(settings, "LLM_VISION_MODELS", ["test/vision"])
    with pytest.raises(ValueError, match="vision"):
        check_vision("test/vision", catalog(False)["data"])


@pytest.mark.parametrize("data", [[], {"data": "bad"}, {"data": [None]}, {"data": [{"id": "test/text"}]}])
def test_startup_rejects_invalid_or_missing_vision_catalog(data):
    with mock_http(lambda request: httpx.Response(200, json=data)), pytest.raises(ValueError):
        with TestClient(app):
            pass


def test_startup_accepts_search_without_api_key():
    with mock_http(lambda request: httpx.Response(200, json=catalog())):
        with TestClient(app) as client:
            assert client.get("/").status_code == 200


@pytest.mark.asyncio
async def test_search_outage_cannot_be_replaced_with_llm_memory():
    with mock_http(lambda request: httpx.Response(401, text="search-key")), pytest.raises(ValueError, match="Search duckduckgo gagal: HTTP 401") as error:
        await llm_service._chat_completion([{"role": "user", "content": "claim"}], web_search=True)
    assert "search-key" not in str(error.value)


def test_legacy_plugin_remains_explicitly_available(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "LLM_WEB_MODE", "plugin")
    assert llm_service._build_payload("model", [], False, True, 0.2, 100)["plugins"][0]["id"] == "web"
    monkeypatch.setattr(settings, "LLM_PROVIDER", "9router")
    payload = llm_service._build_payload("model", [], False, True, 0.2, 100)
    assert "plugins" not in payload and "tools" not in payload


@pytest.mark.parametrize("entry", [
    {"id": "test/vision", "capabilities": {"vision": False}, "input_modalities": ["text", "image"]},
    {"id": "test/vision", "architecture": "malformed"},
])
def test_conflicting_or_malformed_vision_metadata_is_rejected(entry):
    from app.services.provider_service import check_vision
    with pytest.raises(ValueError, match="vision"):
        check_vision("test/vision", [entry])


@pytest.mark.asyncio
async def test_real_transport_pipeline_keeps_quote_and_verdict_contract():
    from unittest.mock import AsyncMock
    from app.services.verification_service import verify_content
    from app.services.analysis_session_service import dispatch, get_session
    source = {"id": "S1", "title": "Arsip", "url": "https://example.com/archive",
              "content": "Proklamasi Indonesia berlangsung pada 17 Agustus 1945.", "image_url": None}
    async def handler(request):
        if request.url.host == "html.duckduckgo.com":
            return httpx.Response(200, text=f'<div class="result"><a class="result__a" href="{source["url"]}">Arsip</a></div>')
        assert request.url.path == "/api/v1/run/text-flow"
        payload = json.loads(request.content)
        input_value = json.loads(payload["input_value"])
        assert set(input_value) == {"analysis_id"}
        session = get_session(input_value["analysis_id"])
        await dispatch(session.id, "ai-call", {"stage": "extract", "max_tokens": 1200})
        await dispatch(session.id, "register", {"claims": ["Indonesia merdeka pada 17 Agustus 1945"], "limitations": []})
        envelope = await dispatch(session.id, "search", {"round": 0, "queries": [{"claim_id": "C1", "query": "Indonesia merdeka 17 Agustus 1945 dukungan bantahan"}]})
        assert envelope["sources"][0]["content"] == [{"passage_id": "P1", "text": source["content"]}]
        await dispatch(session.id, "ai-call", {"stage": "compare", "max_tokens": 2500})
        result = {"claims": [{"claim_id": "C1", "verdict": "SUPPORTED", "reasoning": "Artikel arsip mendukung tanggal tersebut.", "context_issue": None,
                  "supporting_evidence": [{"source_id": "S1", "excerpt": source["content"]}], "contradicting_evidence": [], "limitations": []}], "image_context": None, "indicators": []}
        return httpx.Response(200, json={"outputs": [{"outputs": [{"results": {"message": {"text": json.dumps(result)}}}]}]})
    with mock_http(handler), patch("app.services.verification_service.retrieve_source", AsyncMock(return_value=source)):
        result = await verify_content("Indonesia merdeka pada 17 Agustus 1945")
    assert result.schema_version == "2.0" and result.verdict == "SUPPORTED"
    assert result.claims[0].supporting_evidence[0].excerpt == source["content"]
    assert result.claims[0].supporting_evidence[0].url == source["url"]


@pytest.mark.asyncio
async def test_text_model_fallback_is_preserved(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACK_MODELS", ["test/backup"])
    models = []
    def handler(request):
        model = json.loads(request.content)["model"]
        models.append(model)
        if model == "test/text":
            return httpx.Response(404, json={"error": {"message": "model unavailable"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
    with mock_http(handler):
        content, _ = await llm_service._chat_completion([{"role": "user", "content": "ping"}])
    assert content == "OK" and models == ["test/text", "test/backup"]


@pytest.mark.asyncio
async def test_search_preserves_visual_context_and_reference_date():
    def handler(request):
        query = parse_qs(request.content.decode())["q"][0]
        assert "Foto banjir hari ini" in query
        assert "2026-10-09" in query
        assert "Jembatan merah dengan papan nama" in query
        assert "bukan tanggal kejadian" in query
        return httpx.Response(200, text='<div class="no-results">No results found</div>')
    with mock_http(handler):
        result = await llm_service._chat_completion([{"role": "user", "content": json.dumps({
            "claim": "Foto banjir hari ini", "today": "2026-10-09",
            "visual_observation": "Jembatan merah dengan papan nama"})}], web_search=True)
    assert result == ("", [])
