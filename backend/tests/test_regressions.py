import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.response_models import NewsItem
from app.services.auth_service import AuthUser
from app.services.rate_limit_service import SlidingWindowRateLimiter
from app.services.llm_service import _chat_completion, _build_payload


def test_news_summary_keeps_existing_response_contract():
    article = NewsItem(id="n1", title="Judul berita", link="https://news.google.com/articles/token", source="Media", published="")
    with patch("app.routers.news.get_news_by_id", AsyncMock(return_value=article)), \
         patch("app.routers.news.decode_news_url", AsyncMock(return_value="https://example.com/original")), \
         patch("app.routers.news.scrape_article", AsyncMock(return_value="Konten artikel asli yang cukup panjang untuk diringkas.")), \
         patch("app.routers.news.summarize_article", AsyncMock(return_value="Ringkasan dari isi artikel asli.")):
        response = TestClient(app).get("/news/n1/summarize")
    assert response.status_code == 200
    assert response.json()["original_url"] == "https://example.com/original"
    assert response.json()["summary"] == "Ringkasan dari isi artikel asli."


def test_analyze_rate_limits_still_separate_guest_and_signed_in(monkeypatch):
    from app.dependencies import enforce_analyze_rate_limit, get_current_user
    limiter = SlidingWindowRateLimiter(3600)
    monkeypatch.setattr(settings, "ANON_RATE_LIMIT", 1)
    monkeypatch.setattr(settings, "USER_RATE_LIMIT", 2)
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        with patch("app.dependencies.get_limiter", return_value=limiter):
            client = TestClient(app)
            # Invalid short content still consumes quota as the existing contract does.
            assert client.post("/analyze", json={"text": "short"}).status_code == 400
            assert client.post("/analyze", json={"text": "short"}).status_code == 429
            app.dependency_overrides[get_current_user] = lambda: AuthUser(uid="signed-in-user")
            assert client.post("/analyze", json={"text": "short"}).status_code == 400
            assert client.post("/analyze", json={"text": "short"}).status_code == 400
            response = client.post("/analyze", json={"text": "short"})
            assert response.status_code == 429
            assert "Retry-After" in response.headers
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_vision_failure_never_silently_falls_back_to_text_model(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(settings, "LLM_FALLBACK_MODELS", ["text-only-fallback"])
    original = httpx.AsyncClient
    models = []

    def handler(request):
        models.append(json.loads(request.content)["model"])
        return httpx.Response(400, json={"error": {"message": "Images unsupported"}})

    with patch("app.services.llm_service.httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
        with pytest.raises(ValueError):
            await _chat_completion(messages=[{"role": "user", "content": "test"}], model_override="vision-only")
    assert models == ["vision-only"]


def test_modern_server_search_is_bounded_and_comparison_has_no_tools(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "LLM_WEB_MODE", "server_tool", raising=False)
    monkeypatch.setattr(settings, "LLM_WEB_MAX_RESULTS", 5)
    search = _build_payload("test-model", [], False, True, 0.2, 100)
    assert search["tools"][0]["type"] == "openrouter:web_search"
    assert search["tools"][0]["parameters"]["max_total_results"] == 5
    comparison = _build_payload("test-model", [], True, False, 0.2, 100)
    assert "tools" not in comparison
    assert "plugins" not in comparison
