"""Validate and normalize images in memory, without retaining EXIF or uploads."""
import base64
import binascii
import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MIME_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}


def normalize_image(data_url: str) -> str:
    if len(data_url) > 4 * ((MAX_IMAGE_BYTES + 2) // 3) + 40:
        raise ValueError("Ukuran gambar maksimal 5 MiB")
    try:
        header, encoded = data_url.split(",", 1)
        mime = header.removeprefix("data:").removesuffix(";base64")
        if header != f"data:{mime};base64" or mime not in MIME_FORMATS:
            raise ValueError("Gunakan gambar JPEG, PNG, atau WebP base64")
        data = base64.b64decode(encoded, validate=True)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Ukuran gambar maksimal 5 MiB")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as img:
                if img.format != MIME_FORMATS[mime]:
                    raise ValueError("Jenis file tidak sesuai isi gambar")
                if img.width * img.height > MAX_IMAGE_PIXELS or getattr(img, "n_frames", 1) != 1:
                    raise ValueError("Gunakan gambar diam maksimal 16 megapiksel")
                img.load()
                normalized = ImageOps.exif_transpose(img).convert("RGB")
                normalized.thumbnail((1600, 1600))
                buffer = io.BytesIO()
                # Saving a fresh image intentionally strips uploaded metadata.
                normalized.save(buffer, format="JPEG", quality=90)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError("File gambar tidak valid atau terlalu besar") from exc


def bytes_to_image(data: bytes, mime: str) -> str:
    return normalize_image(f"data:{mime};base64," + base64.b64encode(data).decode("ascii"))
