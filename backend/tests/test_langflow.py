import json
from unittest.mock import patch

import httpx
import pytest

from app.services.analysis_session_service import create_session, close_session
from app.services.langflow_service import run_workflow, LangflowOutputError, LangflowUnavailable, LangflowTimeout

@pytest.mark.asyncio
async def test_langflow_api_session_only_and_nested_chat_output():
    session = create_session(text="private text")
    original = httpx.AsyncClient
    expected = {"claims": [], "image_context": None, "indicators": []}
    def handler(request):
        assert request.url.path == "/api/v1/run/text-flow"
        assert request.headers["x-api-key"] == "unit-flow-key"
        body = json.loads(request.content)
        assert json.loads(body["input_value"]) == {"analysis_id": session.id}
        assert "private text" not in request.content.decode()
        return httpx.Response(200, json={"outputs": [{"outputs": [{"results": {"message": {"text": json.dumps(expected)}}}]}]})
    try:
        with patch("app.services.langflow_service.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)):
            assert await run_workflow(session, "text") == expected
    finally:
        close_session(session.id)

@pytest.mark.asyncio
@pytest.mark.parametrize("data", [{"outputs": []}, {"outputs": [{"outputs": [{"results": {"message": {"text": "[]"}}}]}]}])
async def test_invalid_langflow_output_is_rejected(data):
    session = create_session(); original = httpx.AsyncClient
    try:
        with patch("app.services.langflow_service.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=data)), **kwargs)):
            with pytest.raises(LangflowOutputError): await run_workflow(session, "text")
    finally:
        close_session(session.id)

@pytest.mark.asyncio
@pytest.mark.parametrize("kind,expected", [("invalid_output",LangflowOutputError),("service_unavailable",LangflowUnavailable),("timeout",LangflowTimeout)])
async def test_structured_failures_are_classified_without_secret_echo(kind, expected):
    session = create_session(); original = httpx.AsyncClient
    data = {"outputs": [{"outputs": [{"results": {"message": {"text": json.dumps({"error": {"kind": kind, "stage": "review"}})}}}]}]}
    try:
        with patch("app.services.langflow_service.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=data)), **kwargs)):
            with pytest.raises(expected) as error: await run_workflow(session,"text")
            assert "unit-flow-key" not in str(error.value)
    finally:
        close_session(session.id)
