import httpx
from newspaper import Article


async def scrape_article(url: str) -> str:
    """Scrape article text from a URL using newspaper3k."""
    try:
        # Download the article content
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            html = response.text

        # Parse with newspaper3k
        article = Article(url)
        article.set_html(html)
        article.parse()

        text = article.text
        if not text or len(text.strip()) < 50:
            raise ValueError("Konten artikel terlalu pendek atau tidak dapat diekstrak")

        return text

    except httpx.HTTPError as e:
        raise ValueError(f"Gagal mengakses URL: {str(e)}")
    except Exception as e:
        raise ValueError(f"Gagal mengekstrak artikel: {str(e)}")
