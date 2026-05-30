import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Legacy Google Gemini key (no longer used, kept for backward compat)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    NEWS_CACHE_TTL: int = int(os.getenv("NEWS_CACHE_TTL", "3600"))  # 1 hour

    # OpenRouter (OpenAI-compatible) configuration
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL", "google/gemini-2.0-flash-001"
    )
    # Enable OpenRouter's web search plugin so the fact-checker can verify
    # claims against live internet sources (replaces Google Search Grounding).
    OPENROUTER_WEB_SEARCH: bool = os.getenv(
        "OPENROUTER_WEB_SEARCH", "true"
    ).lower() in ("1", "true", "yes")


settings = Settings()
