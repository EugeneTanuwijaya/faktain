"""Shared FastAPI dependencies: optional auth + rate limiting."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request

from app.config import settings
from app.services import auth_service
from app.services.auth_service import AuthUser
from app.services.rate_limit_service import get_limiter


async def get_current_user(request: Request) -> Optional[AuthUser]:
    """Resolve the signed-in user from the Authorization header, if any.

    Returns ``None`` for anonymous requests. A present-but-invalid token is
    rejected with 401 so clients can surface a clear "please sign in again"
    message instead of silently degrading to the anonymous quota.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None

    if not auth_service.is_enabled():
        # Token supplied but the backend can't verify it. Treat as anonymous
        # rather than failing, so dev setups without Firebase config still work.
        return None

    try:
        return await auth_service.verify_id_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Autentikasi gagal: {exc}")


def _client_ip(request: Request) -> str:
    # X-Forwarded-For = any client-supplied values + the real client IP that
    # Cloud Run appends LAST. Earlier entries are spoofable, so only trust the
    # last one — otherwise anonymous users could forge a fresh "IP" per request
    # and bypass the rate limit.
    # ponytail: assumes direct Cloud Run ingress; behind an extra LB use [-2].
    forwarded = request.headers.get("X-Forwarded-For", "")
    hops = [h.strip() for h in forwarded.split(",") if h.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "unknown"


async def enforce_analyze_rate_limit(
    request: Request,
    user: Optional[AuthUser] = Depends(get_current_user),
) -> Optional[AuthUser]:
    """Apply per-user (signed-in) or per-IP (anonymous) rate limiting.

    Returns the resolved user so routes can reuse it without re-resolving.
    Raises 429 with a ``Retry-After`` header when the quota is exhausted.
    """
    limiter = get_limiter(settings.RATE_LIMIT_WINDOW)

    if user is not None:
        key = f"user:{user.uid}"
        limit = settings.USER_RATE_LIMIT
    else:
        key = f"ip:{_client_ip(request)}"
        limit = settings.ANON_RATE_LIMIT

    result = limiter.check(key, limit)
    if not result.allowed:
        detail = (
            "Batas analisis tercapai. "
            + (
                f"Coba lagi dalam {result.reset_after} detik."
                if user is not None
                else "Masuk dengan akun Google untuk kuota lebih tinggi, "
                f"atau coba lagi dalam {result.reset_after} detik."
            )
        )
        raise HTTPException(
            status_code=429,
            detail=detail,
            headers={
                "Retry-After": str(result.reset_after),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": str(result.remaining),
            },
        )

    return user
