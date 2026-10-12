import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def deterministic_test_settings(monkeypatch):
    from app.services import search_service
    monkeypatch.setattr(search_service, "_blocked_until", 0.0)
    # Unit tests never depend on the developer's external-service settings.
    monkeypatch.setattr(settings, "LLM_WEB_SEARCH", True)
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setattr(settings, "SEARCH_DNS_OVER_HTTPS", False, raising=False)
    monkeypatch.setattr(settings, "LLM_WEB_MAX_RESULTS", 5)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "9router")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://localhost:20128/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "test/text")
    monkeypatch.setattr(settings, "LLM_VISION_MODEL", "test/vision")
    monkeypatch.setattr(settings, "LLM_WEB_MODE", "external")
    monkeypatch.setattr(settings, "ORCHESTRATION_BACKEND", "langflow", raising=False)
    for name,value in {"LANGFLOW_URL": "http://localhost:7860", "LANGFLOW_API_KEY": "unit-flow-key",
                       "LANGFLOW_SERVICE_KEY": "unit-service-key", "LANGFLOW_TEXT_FLOW_ID": "text-flow",
                       "LANGFLOW_IMAGE_FLOW_ID": "image-flow", "LANGFLOW_SUMMARY_FLOW_ID": "summary-flow",
                       "LANGFLOW_NATIVE_FALLBACK": False}.items():
        monkeypatch.setattr(settings, name, value, raising=False)
