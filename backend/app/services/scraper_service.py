import asyncio

import httpx
from newspaper import Article


def _parse_html(url: str, html: str) -> str:
    article = Article(url)
    article.set_html(html)
    article.parse()
    return article.text


async def scrape_article(url: str) -> str:
    """Scrape article text from a URL using newspaper3k."""
    try:
        # Download the article content
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            html = response.text

        # newspaper3k parsing is CPU-heavy; keep it off the event loop.
        text = await asyncio.to_thread(_parse_html, url, html)
        if not text or len(text.strip()) < 50:
            raise ValueError("Konten artikel terlalu pendek atau tidak dapat diekstrak")

        return text

    except httpx.HTTPError as e:
        raise ValueError(f"Gagal mengakses URL: {str(e)}")
    except Exception as e:
        raise ValueError(f"Gagal mengekstrak artikel: {str(e)}")
