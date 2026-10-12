import asyncio
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from newspaper import Article
from app.services.url_safety import safe_fetch


def _parse_html(url: str, html: str) -> str:
    selector = ("#mw-content-text, .mw-parser-output"
                if (urlsplit(url).hostname or "").endswith(".wikipedia.org")
                else '.post-article, .entry-content, [itemprop="articleBody"]')
    # Skip empty style containers; newspaper may select an archive or later section.
    for body in BeautifulSoup(html, "html.parser").select(selector):
        paragraphs = [p.get_text().strip() for p in body.find_all("p") if p.find_parent("table") is None]
        text = "\n\n".join(p for p in paragraphs if p)
        if len(text) >= 50:
            return text
    article = Article(url)
    article.set_html(html)
    article.parse()
    return article.text


async def scrape_article(url: str) -> str:
    """Extract original article text after a bounded, safe URL fetch."""
    try:
        # Download the article content
        data, _, final_url = await safe_fetch(url)
        html = data.decode("utf-8", errors="replace")

        # Article parsing is CPU-heavy; keep it off the event loop.
        text = await asyncio.to_thread(_parse_html, final_url, html)
        if not text or len(text.strip()) < 50:
            raise ValueError("Konten artikel terlalu pendek atau tidak dapat diekstrak")

        return text

    except httpx.HTTPError as e:
        raise ValueError(f"Gagal mengakses URL: {str(e)}")
    except Exception as e:
        raise ValueError(f"Gagal mengekstrak artikel: {str(e)}")
