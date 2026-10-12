from unittest.mock import AsyncMock, patch

import pytest

from app.services.verification_service import verify_content
from app.services.analysis_session_service import dispatch, get_session
from app.services.langflow_service import LangflowUnavailable, LangflowOutputError

SOURCE = {"id": "S1", "title": "Arsip", "url": "https://example.com/archive",
          "content": "Foto banjir Jakarta ini diterbitkan pada Januari 2020.", "image_url": None}


def judged(verdict="SUPPORTED"):
    return {"claims": [{"claim_id": "C1", "verdict": verdict, "reasoning": "Sumber arsip menyebut Januari 2020.",
            "supporting_evidence": [{"source_id": "S1", "excerpt": SOURCE["content"]}], "contradicting_evidence": [], "limitations": [], "context_issue": None}],
            "image_context": None, "indicators": []}

async def register(session, claims, observation=None):
    await dispatch(session.id, "ai-call", {"stage": "observe" if observation is not None else "extract", "max_tokens": 1200})
    value = await dispatch(session.id, "register", {"claims": claims, "observation": observation, "limitations": []})
    if claims:
        await dispatch(session.id, "ai-call", {"stage": "compare", "max_tokens": 2500})
    return value

@pytest.mark.asyncio
async def test_text_runs_through_langflow_and_preserves_backend_provenance():
    snapshots = []
    async def flow(session, kind):
        assert kind == "text"
        snapshots.append(session.id)
        await register(session, ["Foto banjir Jakarta Januari 2020"])
        session.sources = [SOURCE]
        return judged()
    native = AsyncMock(side_effect=AssertionError("normal direct AI is forbidden"))
    with patch("app.services.verification_service.run_workflow", flow), patch("app.services.verification_service._chat_completion", native):
        result = await verify_content("Foto banjir Jakarta Januari 2020")
    assert result.verdict == "SUPPORTED"
    assert result.claims[0].supporting_evidence[0].excerpt == SOURCE["content"]
    assert result.claims[0].supporting_evidence[0].url == SOURCE["url"]
    assert result.orchestration == "langflow" and not native.called
    assert get_session(snapshots[0]) is None

@pytest.mark.asyncio
async def test_no_sources_returns_insufficient_not_model_memory():
    async def flow(session, kind):
        await register(session, ["Sebuah kejadian viral terjadi hari ini"])
        raw = judged("INSUFFICIENT_EVIDENCE"); raw["claims"][0]["supporting_evidence"] = []
        raw["claims"][0]["limitations"] = ["Tidak ada artikel evidence"]
        return raw
    with patch("app.services.verification_service.run_workflow", flow):
        result = await verify_content("Sebuah kejadian viral terjadi hari ini")
    assert result.verdict == "INSUFFICIENT_EVIDENCE" and not result.claims[0].supporting_evidence
    assert result.claims[0].limitations

@pytest.mark.asyncio
async def test_picture_without_explicit_claim_does_not_invent_one():
    async def flow(session, kind):
        assert kind == "image"
        await register(session, [], {"ocr_text": "", "visual_description": "Pepohonan di tepi jalan", "limitations": []})
        return {"claims": [], "image_context": {"verdict": "INSUFFICIENT_EVIDENCE", "reasoning": "Tidak ada klaim faktual", "evidence": []}, "indicators": []}
    with patch("app.services.verification_service.run_workflow", flow):
        result = await verify_content("", image_data_url="data:image/jpeg;base64,test", input_type="image")
    assert not result.claims and result.image_context.verdict == "INSUFFICIENT_EVIDENCE"

@pytest.mark.asyncio
async def test_vision_failure_cannot_guess_caption_claims():
    native = AsyncMock()
    with patch("app.services.verification_service.run_workflow", AsyncMock(side_effect=LangflowUnavailable("vision failed"))), patch("app.services.verification_service._chat_completion", native):
        result = await verify_content("Foto banjir Jakarta Januari 2020", image_data_url="data:image/jpeg;base64,test", input_type="image")
    assert result.image_context.verdict == "INSUFFICIENT_EVIDENCE" and not result.claims
    assert result.limitations and not native.called

@pytest.mark.asyncio
async def test_article_injection_cannot_create_source_url():
    async def flow(session, kind):
        await register(session, ["Foto banjir Jakarta Januari 2020"])
        session.sources = [SOURCE]
        raw = judged(); raw["claims"][0]["supporting_evidence"] = [{"source_id": "made-up", "excerpt": SOURCE["content"], "url": "https://fake.test"}]
        return raw
    with patch("app.services.verification_service.run_workflow", flow): result = await verify_content("Foto banjir Jakarta Januari 2020")
    assert result.verdict == "INSUFFICIENT_EVIDENCE" and result.limitations

@pytest.mark.asyncio
async def test_old_photo_caption_requires_visual_match_and_context_evidence():
    async def flow(session, kind):
        await register(session, ["Foto banjir Jakarta hari ini Oktober 2026"], {"ocr_text": "Banjir hari ini", "visual_description": "Jalan tergenang", "limitations": []})
        session.sources = [SOURCE]; session.matched_source_ids = {"S1"}
        raw = judged("MISLEADING"); item = raw["claims"][0]; item["context_issue"] = "TIME"
        item["contradicting_evidence"] = item.pop("supporting_evidence"); item["supporting_evidence"] = []
        raw["image_context"] = {"verdict": "MISLEADING_CONTEXT", "reasoning": "Foto arsip diberi caption baru", "evidence": [{"source_id": "S1", "excerpt": SOURCE["content"]}]}
        return raw
    with patch("app.services.verification_service.run_workflow", flow):
        result = await verify_content("Foto banjir hari ini", image_data_url="data:image/jpeg;base64,test", input_type="image")
    assert result.verdict == "MISLEADING" and result.image_context.verdict == "MISLEADING_CONTEXT"

@pytest.mark.asyncio
async def test_invalid_shape_degrades_explicitly():
    with patch("app.services.verification_service.run_workflow", AsyncMock(side_effect=LangflowOutputError("bad shape"))):
        result = await verify_content("Sebuah klaim panjang untuk diverifikasi")
    assert result.verdict == "INSUFFICIENT_EVIDENCE" and result.limitations

@pytest.mark.asyncio
async def test_relative_date_is_backend_jakarta_reference():
    async def flow(session, kind):
        context = await dispatch(session.id, "context", {})
        assert context["reference_timezone"] == "Asia/Jakarta"
        assert len(context["reference_date"]) == 10
        await register(session, []); return {"claims": [], "image_context": None, "indicators": []}
    with patch("app.services.verification_service.run_workflow", flow): await verify_content("Banjir terjadi di Jakarta hari ini")
