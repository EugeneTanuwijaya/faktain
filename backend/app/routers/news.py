from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import asyncio
import time

from app.config import settings
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
from app.services.langflow_service import LangflowTimeout, LangflowOutputError, LangflowUnavailable

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
    except Exception:
        raise HTTPException(status_code=500, detail="Gagal mengambil berita. Coba lagi sebentar lagi.") from None

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
    deadline = time.monotonic() + settings.VERIFICATION_TIMEOUT
    try:
        news_item = await asyncio.wait_for(get_news_by_id(news_id), timeout=max(0, deadline - time.monotonic()))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Waktu ringkasan habis saat mengambil berita.") from None
    if not news_item:
        raise HTTPException(status_code=404, detail="Berita tidak ditemukan")

    # Decode the Google News redirect URL to the real publisher URL.
    try:
        real_url = await asyncio.wait_for(decode_news_url(news_item.link), timeout=max(0, deadline - time.monotonic()))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Waktu ringkasan habis saat mengurai tautan berita.") from None
    if not real_url:
        raise HTTPException(
            status_code=502,
            detail="Gagal mengurai tautan Google News ke URL artikel asli",
        )

    # Scrape the actual article text.
    try:
        content = await asyncio.wait_for(scrape_article(real_url), timeout=max(0, deadline - time.monotonic()))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Waktu ringkasan habis saat mengambil artikel asli.") from None

    # Summarize from the scraped text (no grounding needed).
    try:
        summary = await summarize_article(news_item.title, content, timeout=max(0, deadline - time.monotonic()))
    except (LangflowTimeout, TimeoutError):
        raise HTTPException(status_code=504, detail="Waktu ringkasan Langflow habis; seluruh tahap berbagi satu deadline.") from None
    except LangflowOutputError:
        raise HTTPException(status_code=502, detail="Keluaran ringkasan Langflow tidak valid; ringkasan ditolak.") from None
    except LangflowUnavailable:
        raise HTTPException(status_code=503, detail="Layanan ringkasan Langflow tidak tersedia.") from None
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Gagal meringkas artikel. Coba lagi sebentar lagi.",
        ) from None

    return NewsSummaryResponse(
        id=news_item.id,
        title=news_item.title,
        source=news_item.source,
        original_url=real_url,
        summary=summary,
    )
