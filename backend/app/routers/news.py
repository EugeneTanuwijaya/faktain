from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from app.models.response_models import NewsFeedResponse, NewsSummaryResponse
from app.services.news_service import (
    fetch_news,
    get_news_by_id,
    available_categories,
    DEFAULT_CATEGORY,
)
from app.services.scraper_service import scrape_article
from app.services.gnews_decoder import decode_news_url
from app.services.llm_service import summarize_article

router = APIRouter(prefix="/news", tags=["News Feed"])


@router.get("/categories")
async def get_categories():
    """Daftar kategori berita yang tersedia."""
    return {"categories": available_categories()}


@router.get("", response_model=NewsFeedResponse)
async def get_news(limit: int = 20, category: str = DEFAULT_CATEGORY):
    """
    Ambil berita terkini dari Google News Indonesia.

    Parameter `category` memilih feed (terkini, nasional, internasional,
    ekonomi, teknologi, olahraga, hiburan).
    """
    try:
        articles = await fetch_news(limit=limit, category=category)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil berita: {str(e)}")

    return NewsFeedResponse(
        articles=articles,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/{news_id}/summarize", response_model=NewsSummaryResponse)
async def summarize_news_article(news_id: str):
    """
    Ringkas artikel berita dari news feed berdasarkan ID.

    Alur: decode URL Google News -> scrape isi artikel asli -> ringkas dengan
    LLM (tanpa grounding/web search, langsung dari teks artikel).
    """
    news_item = await get_news_by_id(news_id)
    if not news_item:
        raise HTTPException(status_code=404, detail="Berita tidak ditemukan")

    # Decode the Google News redirect URL to the real publisher URL.
    real_url = await decode_news_url(news_item.link)
    if not real_url:
        raise HTTPException(
            status_code=502,
            detail="Gagal mengurai tautan Google News ke URL artikel asli",
        )

    # Scrape the actual article text.
    try:
        content = await scrape_article(real_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Summarize from the scraped text (no grounding needed).
    try:
        summary = await summarize_article(news_item.title, content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal meringkas: {str(e)}",
        )

    return NewsSummaryResponse(
        id=news_item.id,
        title=news_item.title,
        source=news_item.source,
        original_url=real_url,
        summary=summary,
    )
