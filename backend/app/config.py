import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    NEWS_CACHE_TTL: int = int(os.getenv("NEWS_CACHE_TTL", "3600"))  # 1 hour

    # Google Gemini Developer API (AI Studio key, starts with "AIza...").
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_BASE_URL: str = os.getenv(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
    )
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # Enable Grounding with Google Search (free up to 5k requests/month on the
    # free tier). When on, the model verifies claims against live web content.
    GEMINI_GROUNDING: bool = os.getenv("GEMINI_GROUNDING", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    # Cap output tokens to keep responses bounded.
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "4096"))
    # Gemini 2.5+ are "thinking" models that spend tokens on internal reasoning
    # before answering. Limit it so the budget goes to the actual JSON output.
    # 0 disables thinking; values are in tokens.
    GEMINI_THINKING_BUDGET: int = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))
    # Retry handling for 429 (rate limit / quota). The free tier has small
    # per-minute limits (RPM); retrying after the server-provided delay smooths
    # over transient RPM hits. Daily-quota (RPD) exhaustion won't recover here.
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
    # Upper bound (seconds) we're willing to wait for a single Retry-After,
    # so a long RPD-style backoff doesn't hang the request indefinitely.
    GEMINI_MAX_RETRY_WAIT: float = float(os.getenv("GEMINI_MAX_RETRY_WAIT", "60"))


settings = Settings()
