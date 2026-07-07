import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import enforce_analyze_rate_limit
from app.models.request_models import AnalyzeRequest
from app.models.response_models import AnalysisResponse
from app.services.auth_service import AuthUser
from app.services.llm_service import analyze_text
from app.services.scraper_service import scrape_article

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["Analisis"])


@router.post("", response_model=AnalysisResponse)
async def analyze_content(
    request: AnalyzeRequest,
    user: Optional[AuthUser] = Depends(enforce_analyze_rate_limit),
):
    """
    Analisis teks berita atau URL artikel untuk mendeteksi hoaks.
    Kirim salah satu: `text` (teks mentah) atau `url` (URL artikel).

    Verifikasi terbuka untuk umum. Pengunjung anonim dibatasi per IP;
    pengguna yang masuk (Firebase ID token via header Authorization) mendapat
    kuota lebih tinggi.
    """
    if not request.text and not request.url:
        raise HTTPException(
            status_code=400,
            detail="Harus menyertakan 'text' atau 'url' untuk dianalisis",
        )

    # Get text content
    content = request.text
    if request.url:
        try:
            content = await scrape_article(request.url)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    if not content or len(content.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Teks terlalu pendek untuk dianalisis (minimal 20 karakter)",
        )

    # Analyze with the LLM. Log the real error server-side; don't leak
    # upstream/internal details to the public API.
    try:
        result = await analyze_text(content)
    except Exception:
        logger.exception("Analisis gagal")
        raise HTTPException(
            status_code=500,
            detail="Gagal menganalisis. Coba lagi sebentar lagi.",
        )

    # Add snippet of analyzed text
    result["analyzed_text"] = content[:200] + "..." if len(content) > 200 else content

    return AnalysisResponse(**result)
