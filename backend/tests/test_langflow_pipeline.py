import json
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services import verification_service as verification
from app.services import analysis_session_service as sessions


SOURCE = {"id": "S1", "title": "Arsip", "url": "https://example.com/archive",
          "content": "Proklamasi Indonesia berlangsung pada 17 Agustus 1945.", "image_url": None}
CLAIM = "Indonesia merdeka pada 17 Agustus 1945"


@pytest.mark.asyncio
async def test_blocked_search_stops_remaining_queries_and_reports_wait(monkeypatch):
    from app.services import search_service
    session = sessions.create_session(text=CLAIM)
    search = AsyncMock(side_effect=search_service.SearchBlocked("CAPTCHA/challenge DuckDuckGo", 300))
    monkeypatch.setattr(search_service, "search_messages", search)
    try:
        await sessions.dispatch(session.id, "ai-call", {"stage": "extract", "max_tokens": 1200})
        await sessions.dispatch(session.id, "register", {"claims": [CLAIM, "Indonesia memproklamasikan kemerdekaan di Jakarta"]})
        result = await sessions.dispatch(session.id, "search", {"round": 0, "queries": [
            {"claim_id": "C1", "query": "tanggal proklamasi"}, {"claim_id": "C2", "query": "lokasi proklamasi"}]})
        assert search.await_count == 1
        assert any("300 detik" in item and "CAPTCHA" in item for item in result["limitations"])
        assert result["sources"] == [] and session.rounds == 1
    finally:
        sessions.close_session(session.id)


def judgment():
    return {"claims": [{"claim_id": "C1", "verdict": "SUPPORTED", "reasoning": "Artikel menjelaskan tanggal proklamasi.",
                        "supporting_evidence": [{"source_id": "S1", "excerpt": SOURCE["content"]}],
                        "contradicting_evidence": [], "limitations": []}], "image_context": None, "indicators": []}


async def register(session, with_sources=True):
    await sessions.dispatch(session.id, "ai-call", {"stage": "extract", "max_tokens": 1200})
    await sessions.dispatch(session.id, "register", {"claims": [CLAIM], "observation": None})
    if with_sources:
        session.sources.append(dict(SOURCE))


@pytest.mark.asyncio
async def test_normal_verification_uses_langflow_without_direct_model_calls(monkeypatch):
    async def flow(session, kind):
        assert kind == "text"
        await register(session)
        await sessions.dispatch(session.id, "ai-call", {"stage": "compare", "max_tokens": 2500})
        return judgment()
    monkeypatch.setattr(verification, "run_workflow", flow, raising=False)
    direct = AsyncMock(side_effect=AssertionError("Normal AI must not run in backend"))
    monkeypatch.setattr(verification, "_chat_completion", direct)
    result = await verification.verify_content(CLAIM)
    assert result.schema_version == "2.0" and result.orchestration == "langflow"
    assert result.verdict == "SUPPORTED"
    assert result.claims[0].supporting_evidence[0].url == SOURCE["url"]
    direct.assert_not_called()
    assert not sessions._sessions


@pytest.mark.asyncio
async def test_registered_data_survives_langflow_failure_for_comparison_only(monkeypatch):
    from app.services.langflow_service import LangflowUnavailable
    async def flow(session, kind):
        await register(session)
        raise LangflowUnavailable("Langflow unavailable")
    monkeypatch.setattr(verification, "run_workflow", flow, raising=False)
    monkeypatch.setattr(settings, "LANGFLOW_NATIVE_FALLBACK", True)
    direct = AsyncMock(return_value=(json.dumps(judgment()), []))
    monkeypatch.setattr(verification, "_chat_completion", direct)
    result = await verification.verify_content(CLAIM)
    assert result.orchestration == "native_fallback"
    assert result.verdict == "SUPPORTED"
    assert any("Langflow" in limitation for limitation in result.limitations)
    assert direct.call_count == 1
    assert direct.call_args.kwargs["max_attempts"] == 1


@pytest.mark.asyncio
async def test_failed_extraction_cannot_be_replaced_by_native_comparison(monkeypatch):
    from app.services.langflow_service import LangflowOutputError
    monkeypatch.setattr(verification, "run_workflow", AsyncMock(side_effect=LangflowOutputError("Invalid output")), raising=False)
    direct = AsyncMock(side_effect=AssertionError("No extracted claims to compare"))
    monkeypatch.setattr(verification, "_chat_completion", direct)
    result = await verification.verify_content(CLAIM)
    assert result.verdict == "INSUFFICIENT_EVIDENCE" and not result.claims
    assert result.orchestration == "langflow"
    assert any("tidak valid" in limitation for limitation in result.limitations)
    direct.assert_not_called()
    assert not sessions._sessions


@pytest.mark.asyncio
async def test_summary_uses_original_article_in_langflow_session(monkeypatch):
    from app.services import langflow_service
    from app.services.llm_service import summarize_article
    async def flow(session, kind):
        assert kind == "summary" and session.input_type == "summary"
        assert session.article_content == SOURCE["content"]
        assert session.title == "Proklamasi"
        await sessions.dispatch(session.id, "ai-call", {"stage": "summarize", "max_tokens": 500})
        return {"summary": "Artikel membahas proklamasi pada 17 Agustus 1945."}
    monkeypatch.setattr(langflow_service, "run_workflow", flow, raising=False)
    result = await summarize_article("Proklamasi", SOURCE["content"])
    assert result == "Artikel membahas proklamasi pada 17 Agustus 1945."
    assert not sessions._sessions
