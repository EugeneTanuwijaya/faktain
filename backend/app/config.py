import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    NEWS_CACHE_TTL: int = int(os.getenv("NEWS_CACHE_TTL", "3600"))  # 1 hour

    # Firebase Auth (optional). When FIREBASE_PROJECT_ID is set the backend
    # verifies Firebase ID tokens; otherwise every request is treated as
    # anonymous and only IP-based rate limits apply. Usually equal to the GCP
    # project id, but kept explicit so a placeholder project id can't silently
    # enable (and then break) token verification.
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    # Path to a service-account JSON. Optional: on GCP, Application Default
    # Credentials are used automatically when this is empty.
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS", ""
    )

    # Rate limiting for /analyze (sliding window). Anonymous visitors are limited
    # per client IP; signed-in users get a higher quota keyed by their UID.
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1h
    ANON_RATE_LIMIT: int = int(os.getenv("ANON_RATE_LIMIT", "5"))
    USER_RATE_LIMIT: int = int(os.getenv("USER_RATE_LIMIT", "50"))

    # LLM provider: OpenRouter (OpenAI-compatible Chat Completions API).
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "").strip()
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").strip()
    LLM_MODEL: str = os.getenv("LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free").strip()
    # Cap output tokens to keep responses bounded and avoid credit-reservation
    # 402 errors on providers that reserve (prompt + max_tokens) up front.
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    # Web search plugin (OpenRouter). The actual search engine (e.g. Firecrawl)
    # is selected in OpenRouter's dashboard/plugin settings, not here.
    LLM_WEB_SEARCH: bool = os.getenv("LLM_WEB_SEARCH", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    # Max web-search results to request from the plugin per call.
    LLM_WEB_MAX_RESULTS: int = int(os.getenv("LLM_WEB_MAX_RESULTS", "5"))
    # Search engine for the web plugin: "firecrawl" (free, needs dashboard
    # setup), "exa" ($0.005/req), "parallel", "native", or "" (auto).
    LLM_WEB_ENGINE: str = os.getenv("LLM_WEB_ENGINE", "exa")

    # Retry handling for transient 429 (rate limit) and flaky empty responses
    # from free models. Falls back to alternate models when the primary is
    # rate-limited.
    # NOTE: OpenRouter retires :free variants without warning (z-ai/glm-4.5-air
    # died Jul 2026). Check https://openrouter.ai/api/v1/models if analysis
    # starts failing with 404s.
    LLM_FALLBACK_MODELS: list[str] = [
        m.strip()
        for m in os.getenv(
            "LLM_FALLBACK_MODELS",
            "openai/gpt-oss-120b:free,qwen/qwen3-next-80b-a3b-instruct:free",
        ).split(",")
        if m.strip()
    ]
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))


settings = Settings()
