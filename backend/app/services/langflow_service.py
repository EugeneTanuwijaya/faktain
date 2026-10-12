"""Langflow owns normal model calls; FastAPI owns the ephemeral session."""
import asyncio
import json
from urllib.parse import quote

import httpx

from app.config import settings
from app.models.langflow_models import SummaryOutput
from app.services.analysis_session_service import create_session, close_session
from app.services.provider_service import validate_base_url


class LangflowUnavailable(ValueError):
    pass


class LangflowOutputError(ValueError):
    pass


class LangflowTimeout(TimeoutError):
    pass


def validate_langflow_config() -> None:
    if settings.ORCHESTRATION_BACKEND != "langflow":
        raise ValueError("ORCHESTRATION_BACKEND harus langflow; native hanya tersedia sebagai fallback perbandingan")
    for name in ("LANGFLOW_URL", "LANGFLOW_API_KEY", "LANGFLOW_SERVICE_KEY", "LANGFLOW_TEXT_FLOW_ID",
                 "LANGFLOW_IMAGE_FLOW_ID", "LANGFLOW_SUMMARY_FLOW_ID"):
        if not getattr(settings, name):
            raise ValueError(f"{name} belum dikonfigurasi")
    validate_base_url(settings.LANGFLOW_URL, "LANGFLOW_URL")


async def run_workflow(session, kind: str) -> dict:
    flow_id = getattr(settings, f"LANGFLOW_{kind.upper()}_FLOW_ID", "")
    if not settings.LANGFLOW_URL or not settings.LANGFLOW_API_KEY or not flow_id or not settings.LANGFLOW_SERVICE_KEY:
        raise LangflowUnavailable("Langflow belum dikonfigurasi")
    validate_base_url(settings.LANGFLOW_URL, "LANGFLOW_URL")
    if session.remaining_seconds <= 0:
        raise LangflowTimeout("Overall deadline exceeded")
    try:
        async with asyncio.timeout(session.remaining_seconds):
            async with httpx.AsyncClient(timeout=session.remaining_seconds, trust_env=False) as client:
                response = await client.post(f"{settings.LANGFLOW_URL}/api/v1/run/{quote(flow_id, safe='')}",
                    headers={"x-api-key": settings.LANGFLOW_API_KEY},
                    json={"input_type": "chat", "output_type": "chat",
                          "input_value": json.dumps({"analysis_id": session.id}), "session_id": session.id})
                response.raise_for_status()
    except (TimeoutError, httpx.TimeoutException):
        raise LangflowTimeout("Langflow exceeded shared deadline") from None
    except httpx.HTTPError:
        raise LangflowUnavailable("Langflow service unavailable") from None
    try:
        data = response.json()
        message = data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
        if not isinstance(message, str) or len(message) > 100000:
            raise ValueError("Invalid Chat Output")
        result = json.loads(message)
        if not isinstance(result, dict):
            raise ValueError("Expected output object")
    except (KeyError, IndexError, TypeError, ValueError):
        raise LangflowOutputError("Invalid Langflow output") from None
    if "error" in result:
        error = result["error"]
        if not isinstance(error, dict) or set(result) != {"error"} or set(error) != {"kind", "stage"}:
            raise LangflowOutputError("Invalid workflow failure schema")
        if error["kind"] == "timeout":
            raise LangflowTimeout("Workflow shared deadline exceeded")
        if error["kind"] == "invalid_output":
            raise LangflowOutputError("Invalid model or callback output")
        if error["kind"] == "service_unavailable":
            raise LangflowUnavailable("Workflow service unavailable")
        raise LangflowOutputError("Unknown workflow failure")
    return result


async def summarize_with_langflow(title: str, content: str, *, timeout: float | None = None) -> str:
    session = create_session(title=title[:300], article_content=content[:8000], input_type="summary", timeout=timeout)
    try:
        raw = await run_workflow(session, "summary")
        if not session.remaining_seconds:
            raise LangflowTimeout("Overall deadline exceeded")
        if not session.stages.get("summarize"):
            raise LangflowOutputError("Summary stage was not reserved")
        try:
            result = SummaryOutput.model_validate(raw)
        except ValueError:
            raise LangflowOutputError("Invalid summary schema") from None
        if not result.summary.strip():
            raise LangflowOutputError("Empty summary")
        return result.summary.strip()
    finally:
        close_session(session.id)
