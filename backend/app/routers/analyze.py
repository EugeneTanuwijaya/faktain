import logging
import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import enforce_analyze_rate_limit
from app.models.request_models import AnalyzeRequest
from app.config import settings
from app.models.verification_models import VerificationResponse
from app.services.auth_service import AuthUser
from app.services.verification_service import verify_content
from app.services.image_service import normalize_image
from app.services.evidence_service import normalize_result
from app.services.scraper_service import scrape_article

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["Analisis"])


@router.post("", response_model=VerificationResponse)
async def analyze_content(
    request: AnalyzeRequest,
    user: Optional[AuthUser] = Depends(enforce_analyze_rate_limit),
):
    """
    Verifikasi evidence dari teks, URL atau gambar dengan caption opsional.

    Verifikasi terbuka untuk umum. Pengunjung anonim dibatasi per IP;
    pengguna yang masuk (Firebase ID token via header Authorization) mendapat
    kuota lebih tinggi.
    """
    deadline = time.monotonic() + settings.VERIFICATION_TIMEOUT
    content = request.text or ""
    image = None
    input_type = "image" if request.image_data_url else "url" if request.url else "text"
    if request.image_data_url:
        try:
            image = await asyncio.wait_for(asyncio.to_thread(normalize_image, request.image_data_url),
                                           timeout=max(0, deadline - time.monotonic()))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except TimeoutError:
            raise HTTPException(status_code=422, detail="Waktu verifikasi habis saat menyiapkan gambar.") from None
    if request.url:
        try:
            content = await asyncio.wait_for(scrape_article(request.url),
                                             timeout=min(15.0, max(0, deadline - time.monotonic())))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except TimeoutError:
            raise HTTPException(status_code=422, detail="Pengambilan artikel terlalu lama. Coba tempel teksnya.")

    if not image and len(content.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Teks terlalu pendek untuk dianalisis (minimal 20 karakter)",
        )

    # Exception messages and tracebacks may include provider or input payloads.
    try:
        result = await verify_content(content, image_data_url=image, input_type=input_type,
                                      timeout=max(0, deadline - time.monotonic()))
    except TimeoutError:
        result = normalize_result({}, [], [], observation={} if image else None, input_type=input_type, orchestration="langflow",
                                  limitations=["Waktu verifikasi habis; pengambilan dan perbandingan evidence belum selesai. Silakan ulangi."])
    except Exception as exc:
        logger.warning("Analisis gagal (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Gagal menganalisis. Coba lagi sebentar lagi.",
        )

    # Add snippet of analyzed text
    result.analyzed_text = content[:300]
    return result
