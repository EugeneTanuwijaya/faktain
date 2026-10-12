"""Configuration, catalog health and explicit image capability checks."""
from urllib.parse import urlsplit

import httpx

from app.config import settings


def validate_base_url(value: str, name: str) -> None:
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in {"http", "https"} and parsed.hostname and parsed.port != 0
    except ValueError:
        valid = False
    if not valid or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError(f"{name} harus URL HTTP/HTTPS valid tanpa credentials/query/fragment")


def validate_llm_config() -> None:
    for name in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        if not getattr(settings, name).strip():
            raise ValueError(f"{name} belum diset. Konfigurasikan backend/.env")
    validate_base_url(settings.LLM_BASE_URL, "LLM_BASE_URL")
    if settings.LLM_MAX_RETRIES < 1 or settings.LLM_HEALTH_TIMEOUT <= 0:
        raise ValueError("LLM_MAX_RETRIES dan LLM_HEALTH_TIMEOUT harus positif")


def llm_headers() -> dict:
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"}
    if settings.LLM_PROVIDER == "openrouter":
        headers.update({"HTTP-Referer": settings.FRONTEND_URL, "X-Title": "FAKTANYA"})
    return headers


async def model_catalog() -> list[dict]:
    validate_llm_config()
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_HEALTH_TIMEOUT) as client:
            response = await client.get(f"{settings.LLM_BASE_URL.rstrip('/')}/models", headers=llm_headers())
    except httpx.HTTPError as exc:
        raise ValueError(f"Provider {settings.LLM_PROVIDER} tidak dapat dijangkau ({type(exc).__name__}); periksa LLM_BASE_URL dan layanan router") from exc
    if response.status_code != 200:
        # Never expose upstream response bodies, which may contain credentials.
        raise ValueError(f"Provider {settings.LLM_PROVIDER}: GET /models gagal HTTP {response.status_code}; periksa API key dan akses model")
    try:
        data = response.json()["data"]
        if not isinstance(data, list) or any(not isinstance(m, dict) or not isinstance(m.get("id"), str) for m in data):
            raise ValueError("invalid model list")
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Provider {settings.LLM_PROVIDER}: katalog /models tidak valid") from exc
    return data


def check_vision(model: str, catalog: list[dict]) -> None:
    entry = next((m for m in catalog if m["id"] == model), None)
    if entry is None:
        raise ValueError(f"Model vision '{model}' tidak tersedia di /models")
    caps = entry.get("capabilities") or {}
    architecture = entry.get("architecture") or {}
    if not isinstance(caps, dict) or not isinstance(architecture, dict):
        raise ValueError(f"Metadata vision model '{model}' tidak valid")
    modalities = architecture.get("input_modalities", entry.get("input_modalities"))
    supported = caps.get("vision")
    if supported is False or (isinstance(modalities, list) and "image" not in modalities):
        raise ValueError(f"Model '{model}' tidak mendukung vision/image input")
    if supported is True or (isinstance(modalities, list) and "image" in modalities):
        return
    if model not in settings.LLM_VISION_MODELS:
        raise ValueError(f"Dukungan vision model '{model}' belum dikonfirmasi; periksa dokumentasi upstream lalu isi LLM_VISION_MODELS jika metadata tidak tersedia")


async def validate_vision_model(model: str) -> None:
    # Recheck before image input; do not trust a text fallback or name heuristic.
    check_vision(model, await model_catalog())


async def provider_health() -> dict:
    catalog = await model_catalog()
    ids = {m["id"] for m in catalog}
    for model in [settings.LLM_MODEL, *settings.LLM_FALLBACK_MODELS]:
        if model not in ids:
            raise ValueError(f"Model '{model}' tidak tersedia di provider {settings.LLM_PROVIDER} /models")
    if not settings.LLM_VISION_MODEL:
        raise ValueError("LLM_VISION_MODEL belum diset; pilih model yang mendukung vision")
    check_vision(settings.LLM_VISION_MODEL, catalog)
    return {"status": "healthy", "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL, "vision_model": settings.LLM_VISION_MODEL}
