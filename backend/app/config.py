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

    # OpenAI-compatible provider. Model IDs are local to the configured router.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "9router").strip().lower()
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:20128/v1").strip()
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "").strip()
    LLM_MODEL: str = os.getenv("LLM_MODEL", "").strip()
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    LLM_FALLBACK_MODELS: list[str] = [m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if m.strip()]
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_HEALTH_TIMEOUT: float = float(os.getenv("LLM_HEALTH_TIMEOUT", "10"))

    # Images never fall back to text models. Explicit list is only used when
    # the catalog omits vision metadata; operator must verify upstream support.
    LLM_VISION_MODEL: str = os.getenv("LLM_VISION_MODEL", "").strip()
    LLM_VISION_MODELS: list[str] = [m.strip() for m in os.getenv("LLM_VISION_MODELS", "").split(",") if m.strip()]

    LLM_WEB_SEARCH: bool = os.getenv("LLM_WEB_SEARCH", "true").lower() in ("1", "true", "yes")
    LLM_WEB_MAX_RESULTS: int = int(os.getenv("LLM_WEB_MAX_RESULTS", "5"))
    # Independent search service for 9Router; legacy modes only for OpenRouter.
    SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "duckduckgo").strip().lower()
    SEARCH_DNS_OVER_HTTPS: bool = os.getenv("SEARCH_DNS_OVER_HTTPS", "false").lower() in ("1", "true", "yes")
    LLM_WEB_ENGINE: str = os.getenv("LLM_WEB_ENGINE", "exa").strip()
    LLM_WEB_MODE: str = os.getenv("LLM_WEB_MODE", "external").strip().lower()
    VERIFICATION_TIMEOUT: float = float(os.getenv("VERIFICATION_TIMEOUT", "100"))
    VERIFICATION_MAX_CLAIMS: int = 3
    VERIFICATION_MAX_SOURCES: int = 5
    VERIFICATION_MAX_SOURCE_IMAGES: int = 2
    ORCHESTRATION_BACKEND: str = os.getenv("ORCHESTRATION_BACKEND", "langflow").strip().lower()
    LANGFLOW_URL: str = os.getenv("LANGFLOW_URL", "").strip().rstrip("/")
    LANGFLOW_FLOW_ID: str = os.getenv("LANGFLOW_FLOW_ID", "").strip()
    LANGFLOW_API_KEY: str = os.getenv("LANGFLOW_API_KEY", "").strip()
    LANGFLOW_TEXT_FLOW_ID: str = os.getenv("LANGFLOW_TEXT_FLOW_ID", "").strip()
    LANGFLOW_IMAGE_FLOW_ID: str = os.getenv("LANGFLOW_IMAGE_FLOW_ID", "").strip()
    LANGFLOW_SUMMARY_FLOW_ID: str = os.getenv("LANGFLOW_SUMMARY_FLOW_ID", "").strip()
    LANGFLOW_SERVICE_KEY: str = os.getenv("LANGFLOW_SERVICE_KEY", "").strip()
    LANGFLOW_NATIVE_FALLBACK: bool = os.getenv("LANGFLOW_NATIVE_FALLBACK", "true").lower() in ("1", "true", "yes")
    VERIFICATION_MAX_AI_CALLS: int = 8
    VERIFICATION_MAX_OUTPUT_TOKENS: int = 10000


settings = Settings()
