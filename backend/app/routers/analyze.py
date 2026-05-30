from fastapi import APIRouter, HTTPException
from app.models.request_models import AnalyzeRequest
from app.models.response_models import AnalysisResponse
from app.services.gemini_service import analyze_text
from app.services.scraper_service import scrape_article

router = APIRouter(prefix="/analyze", tags=["Analisis"])


@router.post("", response_model=AnalysisResponse)
async def analyze_content(request: AnalyzeRequest):
    """
    Analisis teks berita atau URL artikel untuk mendeteksi hoaks.
    Kirim salah satu: `text` (teks mentah) atau `url` (URL artikel).
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

    # Analyze with Gemini
    try:
        result = await analyze_text(content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menganalisis: {str(e)}",
        )

    # Add snippet of analyzed text
    result["analyzed_text"] = content[:200] + "..." if len(content) > 200 else content

    return AnalysisResponse(**result)
