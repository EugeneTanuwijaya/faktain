"""Firebase ID token verification.

Verifies Firebase Authentication ID tokens (signed JWTs) using Google's public
x509 certificates, without pulling in the heavy ``firebase-admin`` SDK. Only
``PyJWT`` + ``cryptography`` are required.

The module is deliberately *optional*: when ``FIREBASE_PROJECT_ID`` is not
configured, verification is skipped and callers should treat the request as
anonymous. This keeps local development friction-free while still allowing a
fully authenticated deployment.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from app.config import settings

# Google's public certs for Firebase ID tokens (RS256, x509).
_CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
_ISSUER_PREFIX = "https://securetoken.google.com/"


@dataclass(frozen=True)
class AuthUser:
    """A verified, signed-in user."""

    uid: str
    email: Optional[str] = None
    name: Optional[str] = None


class _CertCache:
    """Caches Google's signing certs, honouring the HTTP Cache-Control max-age."""

    def __init__(self) -> None:
        self._certs: dict[str, str] = {}
        self._expires_at: float = 0.0

    async def get(self) -> dict[str, str]:
        if self._certs and time.time() < self._expires_at:
            return self._certs

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_CERTS_URL)
            resp.raise_for_status()
            self._certs = resp.json()

        # Respect max-age so we refresh certs roughly when Google rotates them.
        max_age = 3600
        cache_control = resp.headers.get("Cache-Control", "")
        for part in cache_control.split(","):
            part = part.strip()
            if part.startswith("max-age="):
                try:
                    max_age = int(part.split("=", 1)[1])
                except ValueError:
                    pass
        self._expires_at = time.time() + max_age
        return self._certs


_cert_cache = _CertCache()


def is_enabled() -> bool:
    """True when Firebase token verification is configured."""
    return bool(settings.FIREBASE_PROJECT_ID)


async def verify_id_token(id_token: str) -> AuthUser:
    """Verify a Firebase ID token and return the authenticated user.

    Raises ``ValueError`` if the token is missing, malformed, expired, or fails
    signature/claim validation.
    """
    if not id_token:
        raise ValueError("Token kosong")

    project_id = settings.FIREBASE_PROJECT_ID
    if not project_id:
        raise ValueError("Verifikasi Firebase tidak dikonfigurasi")

    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError as exc:
        raise ValueError(f"Header token tidak valid: {exc}") from exc

    kid = header.get("kid")
    if not kid:
        raise ValueError("Token tidak memiliki 'kid'")

    certs = await _cert_cache.get()
    cert = certs.get(kid)
    if not cert:
        # Cert may have rotated; force a refresh once before giving up.
        _cert_cache._expires_at = 0.0
        certs = await _cert_cache.get()
        cert = certs.get(kid)
    if not cert:
        raise ValueError("Kunci penanda tangan token tidak dikenal")

    public_key = RSAAlgorithm.from_jwk(_x509_to_jwk(cert))

    try:
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"{_ISSUER_PREFIX}{project_id}",
        )
    except jwt.PyJWTError as exc:
        raise ValueError(f"Token tidak valid: {exc}") from exc

    # Firebase puts the user id in 'sub' (and mirrors it in 'user_id').
    uid = claims.get("sub") or claims.get("user_id")
    if not uid:
        raise ValueError("Token tidak memiliki subjek (uid)")

    return AuthUser(
        uid=uid,
        email=claims.get("email"),
        name=claims.get("name"),
    )


def _x509_to_jwk(cert_pem: str) -> str:
    """Convert an x509 PEM certificate to a JWK string for PyJWT."""
    from cryptography.x509 import load_pem_x509_certificate

    # PyJWT's RSAAlgorithm.from_jwk wants a JWK; build it from the cert's key.
    import json

    cert = load_pem_x509_certificate(cert_pem.encode("utf-8"))
    public_key = cert.public_key()
    jwk = RSAAlgorithm.to_jwk(public_key)
    # to_jwk returns a JSON string already; pass through.
    return jwk if isinstance(jwk, str) else json.dumps(jwk)
