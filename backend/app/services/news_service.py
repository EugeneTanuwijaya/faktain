import asyncio
import feedparser
import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from app.config import settings
from app.models.response_models import NewsItem

# Default top-headlines feed for Indonesia.
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss?hl=id&gl=ID&ceid=ID:id"

# Category feeds. Google News "topic" feeds are unreliable for id-ID, so we use
# the search feed with a representative query per category. "when:7d" keeps the
# results fresh (last 7 days).
_CEID = "hl=id&gl=ID&ceid=ID:id"
CATEGORY_FEEDS: dict[str, str] = {
    "terkini": GOOGLE_NEWS_RSS_URL,
    "nasional": f"https://news.google.com/rss/search?q=Indonesia+nasional+when:7d&{_CEID}",
    "internasional": f"https://news.google.com/rss/search?q=internasional+dunia+when:7d&{_CEID}",
    "ekonomi": f"https://news.google.com/rss/search?q=ekonomi+bisnis+when:7d&{_CEID}",
    "teknologi": f"https://news.google.com/rss/search?q=teknologi+when:7d&{_CEID}",
    "olahraga": f"https://news.google.com/rss/search?q=olahraga+when:7d&{_CEID}",
    "hiburan": f"https://news.google.com/rss/search?q=hiburan+selebriti+when:7d&{_CEID}",
}

DEFAULT_CATEGORY = "terkini"

# In-memory cache, keyed by category.
_news_cache: dict[str, dict] = {}


def _generate_id(link: str) -> str:
    """Generate a short ID from the article link."""
    return hashlib.md5(link.encode()).hexdigest()[:12]


def _parse_entries(feed, limit: int) -> List[NewsItem]:
    articles: List[NewsItem] = []
    for entry in feed.entries[:limit]:
        # Extract source from title (Google News format: "Title - Source").
        title = entry.get("title", "")
        source = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0]
            source = parts[1] if len(parts) > 1 else ""

        # Some search feeds expose the source name explicitly.
        if not source and entry.get("source") and entry.source.get("title"):
            source = entry.source.title

        published = entry.get("published", "")

        image_url = None
        if hasattr(entry, "media_content") and entry.media_content:
            image_url = entry.media_content[0].get("url")

        articles.append(
            NewsItem(
                id=_generate_id(entry.get("link", "")),
                title=title,
                link=entry.get("link", ""),
                source=source,
                published=published,
                summary=None,
                image_url=image_url,
            )
        )
    return articles


async def fetch_news(limit: int = 20, category: str = DEFAULT_CATEGORY) -> List[NewsItem]:
    """Fetch latest Indonesian news from Google News RSS for a given category."""
    category = (category or DEFAULT_CATEGORY).lower()
    if category not in CATEGORY_FEEDS:
        category = DEFAULT_CATEGORY

    # Check cache (TTL per category).
    cached = _news_cache.get(category)
    if cached:
        cache_age = (datetime.now(timezone.utc) - cached["timestamp"]).total_seconds()
        if cache_age < settings.NEWS_CACHE_TTL:
            return cached["articles"][:limit]

    # feedparser does a blocking HTTP fetch; keep it off the event loop.
    feed = await asyncio.to_thread(feedparser.parse, CATEGORY_FEEDS[category])
    # Fetch a generous pool so different limits can be served from one cache entry.
    articles = _parse_entries(feed, max(limit, 30))

    _news_cache[category] = {
        "articles": articles,
        "timestamp": datetime.now(timezone.utc),
    }

    return articles[:limit]


async def get_news_by_id(news_id: str) -> Optional[NewsItem]:
    """Get a specific news item by ID from any cached category."""
    if not _news_cache:
        await fetch_news()

    for cached in _news_cache.values():
        for article in cached["articles"]:
            if article.id == news_id:
                return article

    return None


def available_categories() -> List[str]:
    """Return the list of supported category keys."""
    return list(CATEGORY_FEEDS.keys())
