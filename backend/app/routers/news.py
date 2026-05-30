from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from app.models.response_models import NewsFeedResponse, AnalysisResponse
from app.services.news_service import fetch_news, get_news_by_id
from app.services.scraper_service import scrape_article
from app.services.gemini_service import analyze_text

router = APIRouter(prefix="/news", tags=["News Feed"])


@router.get("", response_model=NewsFeedResponse)
async def get_news(limit: int = 20):
    """
    Ambil berita terkini dari Google News Indonesia.
    """
    try:
        articles = await fetch_news(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil berita: {str(e)}")

    return NewsFeedResponse(
        articles=articles,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/{news_id}/analyze", response_model=AnalysisResponse)
async def analyze_news_article(news_id: str):
    """
    Analisis artikel berita dari news feed berdasarkan ID.
    """
    news_item = await get_news_by_id(news_id)
    if not news_item:
        raise HTTPException(status_code=404, detail="Berita tidak ditemukan")

    # Scrape the article
    try:
        content = await scrape_article(news_item.link)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Analyze with Gemini
    try:
        result = await analyze_text(content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menganalisis: {str(e)}",
        )

    result["analyzed_text"] = content[:200] + "..." if len(content) > 200 else content

    return AnalysisResponse(**result)
