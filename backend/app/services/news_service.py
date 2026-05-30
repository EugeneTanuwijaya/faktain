import feedparser
import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from app.models.response_models import NewsItem

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss?hl=id&gl=ID&ceid=ID:id"

# In-memory cache
_news_cache: Optional[dict] = None


def _generate_id(link: str) -> str:
    """Generate a short ID from the article link."""
    return hashlib.md5(link.encode()).hexdigest()[:12]


async def fetch_news(limit: int = 20) -> List[NewsItem]:
    """Fetch latest Indonesian news from Google News RSS."""
    global _news_cache

    # Check cache
    if _news_cache:
        cache_age = (datetime.now(timezone.utc) - _news_cache["timestamp"]).seconds
        if cache_age < 3600:  # 1 hour TTL
            return _news_cache["articles"][:limit]

    feed = feedparser.parse(GOOGLE_NEWS_RSS_URL)
    articles: List[NewsItem] = []

    for entry in feed.entries[:limit]:
        # Extract source from title (Google News format: "Title - Source")
        title = entry.get("title", "")
        source = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0]
            source = parts[1] if len(parts) > 1 else ""

        published = entry.get("published", "")

        # Try to get image from media content
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

    # Update cache
    _news_cache = {
        "articles": articles,
        "timestamp": datetime.now(timezone.utc),
    }

    return articles


async def get_news_by_id(news_id: str) -> Optional[NewsItem]:
    """Get a specific news item by ID from cache."""
    if not _news_cache:
        await fetch_news()

    if _news_cache:
        for article in _news_cache["articles"]:
            if article.id == news_id:
                return article

    return None
