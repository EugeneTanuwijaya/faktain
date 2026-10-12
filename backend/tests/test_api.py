from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import enforce_analyze_rate_limit
from app.services.evidence_service import normalize_result
from app.config import settings
import base64
import io
from PIL import Image

client = TestClient(app)


def test_existing_text_route_returns_new_contract_with_no_score():
    app.dependency_overrides[enforce_analyze_rate_limit] = lambda: None
    try:
        result = normalize_result({}, ["Berita ini belum memiliki cukup bukti"], [])
        with patch("app.routers.analyze.verify_content", AsyncMock(return_value=result)):
            response = client.post("/analyze", json={"text": "Berita ini belum memiliki cukup bukti"})
        assert response.status_code == 200
        assert response.json()["schema_version"] == "2.0"
        assert "confidence_score" not in response.json()
    finally:
        app.dependency_overrides.clear()


def test_url_route_still_scrapes_before_verification():
    app.dependency_overrides[enforce_analyze_rate_limit] = lambda: None
    try:
        result = normalize_result({}, ["Berita di artikel ini belum bisa dipastikan"], [], input_type="url")
        with patch("app.routers.analyze.scrape_article", AsyncMock(return_value="Isi artikel dengan klaim yang perlu diperiksa.")), \
             patch("app.routers.analyze.verify_content", AsyncMock(return_value=result)) as verify:
            response = client.post("/analyze", json={"url": "https://example.com/article"})
        assert response.status_code == 200
        assert response.json()["input_type"] == "url"
        assert "Isi artikel" in verify.call_args.args[0]
    finally:
        app.dependency_overrides.clear()


def test_invalid_image_is_rejected_before_provider():
    app.dependency_overrides[enforce_analyze_rate_limit] = lambda: None
    try:
        with patch("app.routers.analyze.verify_content", AsyncMock()) as verify:
            response = client.post("/analyze", json={"image_data_url": "data:image/png;base64,bad"})
        assert response.status_code == 422
        verify.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_health_and_news_categories_preserved():
    assert client.get("/health").json() == {"status": "healthy"}
    assert "nasional" in client.get("/news/categories").json()["categories"]


def test_request_validation_returns_readable_error_without_echoing_input():
    response = client.post("/analyze", json={"text": "private caption", "url": "https://example.com"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert "private caption" not in response.text


def test_real_pipeline_without_provider_key_returns_insufficiency_for_image(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    app.dependency_overrides[enforce_analyze_rate_limit] = lambda: None
    try:
        response = client.post("/analyze", json={"image_data_url": data_url, "text": "Foto banjir Jakarta hari ini"})
        assert response.status_code == 200
        result = response.json()
        assert result["verdict"] == "INSUFFICIENT_EVIDENCE"
        assert result["image_context"]["verdict"] == "INSUFFICIENT_EVIDENCE"
        assert result["limitations"]
        assert not result["claims"]
    finally:
        app.dependency_overrides.clear()
