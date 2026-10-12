"""Langflow verification with a bounded native comparison fallback."""
import asyncio
import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from fastapi import HTTPException

from app.config import settings
from app.models.verification_models import VerificationResponse
from app.models.langflow_models import validate_comparison
from app.services.evidence_service import normalize_result
from app.services.llm_service import _chat_completion
from app.services.scraper_service import _parse_html
from app.services.url_safety import safe_fetch
from app.services.analysis_session_service import create_session, close_session, reserve_fallback
from app.services.langflow_service import run_workflow, LangflowUnavailable, LangflowOutputError, LangflowTimeout
from app.services.verification_prompts import SAFETY, EXTRACTION, VISION, comparison_prompt


async def retrieve_source(citation: dict, source_id: str) -> dict:
    data, _, final_url = await safe_fetch(citation["url"])
    html = data.decode("utf-8", errors="replace")
    text = await asyncio.to_thread(_parse_html, final_url, html)
    if len(text.strip()) < 50:
        raise ValueError("Isi sumber tidak dapat diekstrak")
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else str(citation.get("title", "Sumber"))
    image_tag = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
    image_url = urljoin(final_url, image_tag.get("content", "")) if image_tag and image_tag.get("content") else None
    return {"id": source_id, "title": title[:300], "url": final_url, "content": text[:10000], "image_url": image_url}

async def _native_comparison(session) -> dict:
    budget = await reserve_fallback(session)
    content, _ = await asyncio.wait_for(
        _chat_completion(json_mode=True, require_json=True, max_tokens=2500,
            model_override=settings.LLM_MODEL, max_attempts=1,
            messages=[{"role": "system", "content": SAFETY + comparison_prompt(session.input_type == "image")},
                      {"role": "user", "content": json.dumps(session.envelope(), ensure_ascii=False)}]),
        timeout=budget["remaining_seconds"])
    return validate_comparison(json.loads(content), session.claims, session.sources,
                               is_image=session.input_type == "image")


async def verify_content(text: str, *, image_data_url: str | None = None, input_type: str = "text",
                         timeout: float | None = None) -> VerificationResponse:
    session = create_session(text=text, image_data_url=image_data_url, input_type=input_type, timeout=timeout)
    raw, mode = {}, "langflow"
    try:
        try:
            raw = await run_workflow(session, "image" if image_data_url else "text")
            if not session.remaining_seconds:
                raise LangflowTimeout("Overall deadline exceeded")
            if not session.registered:
                raise LangflowOutputError("No registered extraction snapshot")
            if session.claims and not session.stages.get("compare"):
                raise LangflowOutputError("Comparison stage was not reserved")
            raw = validate_comparison(raw, session.claims, session.sources, is_image=bool(image_data_url))
        except (LangflowUnavailable, LangflowOutputError, TimeoutError, ValueError) as exc:
            if isinstance(exc, (LangflowTimeout, TimeoutError)):
                limitation = "Waktu verifikasi Langflow habis; seluruh tahap berbagi satu deadline."
            elif isinstance(exc, LangflowUnavailable):
                limitation = "Layanan Langflow atau layanan model/bukti tidak tersedia; pemeriksaan belum selesai."
            else:
                limitation = "Keluaran model/flow Langflow tidak valid; hasil tahap tersebut ditolak."
            session.limitations.append(limitation)
            if not session.registered:
                session.limitations.append(
                    "OCR/pengamatan visual belum berhasil diselesaikan; teks atau konteks gambar tidak ditebak."
                    if image_data_url else "Ekstraksi klaim belum berhasil diselesaikan; klaim tidak dibuat dari tebakan.")
            raw = {}
            if settings.LANGFLOW_NATIVE_FALLBACK and session.claims and session.sources and session.remaining_seconds:
                try:
                    raw = await _native_comparison(session)
                    mode = "native_fallback"
                    session.limitations.append("Langflow gagal; hanya perbandingan memakai fallback native dengan klaim dan evidence yang sudah tersedia.")
                except (ValueError, TimeoutError, HTTPException):
                    if session.stages.get("native_fallback"):
                        mode = "native_fallback"
                    session.limitations.append("Fallback perbandingan tidak tersedia, anggaran habis, atau keluarannya tidak valid; tidak ada kesimpulan dari ingatan model.")
        observation = session.observation if session.observation is not None else {} if image_data_url else None
        result = normalize_result(raw, session.claims, session.sources, observation=observation,
            matched_source_ids=session.matched_source_ids, limitations=session.limitations,
            input_type=input_type, orchestration=mode)
        result.analyzed_text = text[:300]
        return result
    finally:
        close_session(session.id)
