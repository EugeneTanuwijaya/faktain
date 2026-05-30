import json
import httpx

from app.config import settings

# OpenRouter exposes an OpenAI-compatible Chat Completions API.
# We talk to it directly with httpx so we don't need the openai SDK.
_CHAT_COMPLETIONS_URL = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"

# Recommended (optional) attribution headers for OpenRouter.
_DEFAULT_HEADERS = {
    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": settings.FRONTEND_URL,
    "X-Title": "Anti-Hoax",
}


async def _chat_completion(
    messages: list[dict],
    *,
    json_mode: bool = False,
    web_search: bool = False,
    temperature: float = 0.2,
) -> str:
    """Call OpenRouter chat completions and return the assistant message text."""
    if not settings.OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY belum diset. Tambahkan key OpenRouter di backend/.env"
        )

    payload: dict = {
        "model": settings.OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    # OpenRouter's "web" plugin performs live internet search and injects the
    # results into the prompt. This replaces Google's Search Grounding tool.
    if web_search and settings.OPENROUTER_WEB_SEARCH:
        payload["plugins"] = [{"id": "web"}]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            _CHAT_COMPLETIONS_URL,
            headers=_DEFAULT_HEADERS,
            json=payload,
        )

    if resp.status_code != 200:
        # Surface OpenRouter's error message to make debugging easier.
        try:
            err = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            err = resp.text
        raise ValueError(f"OpenRouter error {resp.status_code}: {err}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Respons OpenRouter tidak terduga: {data}") from e


ANALYSIS_PROMPT = """Kamu adalah fact-checker profesional yang berspesialisasi pada 
berita dan informasi di Indonesia.

## Tugasmu:
1. Analisis teks berita berikut untuk mendeteksi pola hoaks
2. Identifikasi klaim-klaim utama yang perlu diverifikasi  
3. Cari di internet untuk mengkonfirmasi atau membantah klaim tersebut
4. Bandingkan dengan sumber berita terpercaya Indonesia:
   Kompas, Tempo, CNN Indonesia, BBC Indonesia, Antara
5. Cek apakah berita ini sudah pernah dibantah di 
   Turnbackhoax.id, Cekfakta.com, atau AFP Fact Check Indonesia

## Indikator yang harus dicek:
- Judul clickbait (kata seperti MENGEJUTKAN, TERBUKTI, VIRAL, dll)
- Klaim absolut tanpa sumber yang bisa diverifikasi
- Bahasa emosional berlebihan atau memperkeruh polarisasi
- Atribusi sumber yang tidak jelas ("menurut para ahli...")
- Inkonsistensi internal (tanggal, angka, fakta yang kontradiktif)
- Narasi SARA yang tidak berimbang
- Urgensi artifisial ("sebarkan sebelum dihapus!")

## Format output (JSON ketat, tanpa teks di luar JSON):
{
  "confidence_score": <angka 0-100>,
  "verdict": "<KREDIBEL | PERLU DICEK | KEMUNGKINAN HOAKS>",
  "reasoning": "<penjelasan singkat 2-3 kalimat>",
  "indicators": [
    {
      "type": "<jenis indikator>",
      "description": "<penjelasan>",
      "severity": "<low | medium | high>"
    }
  ],
  "verified_claims": [
    {
      "claim": "<klaim yang diekstrak>",
      "status": "<TERKONFIRMASI | DIBANTAH | TIDAK DAPAT DIVERIFIKASI>",
      "explanation": "<penjelasan hasil verifikasi>"
    }
  ],
  "sources_found": [
    {
      "title": "<judul sumber>",
      "url": "<URL>",
      "credibility": "<TERPERCAYA | NETRAL | MERAGUKAN>"
    }
  ],
  "suggestion": "<saran verifikasi lebih lanjut untuk user>"
}

## Teks yang dianalisis:
"""


async def analyze_text(text: str) -> dict:
    """Analyze text using an OpenRouter model with live web search."""
    content = await _chat_completion(
        messages=[
            {"role": "user", "content": ANALYSIS_PROMPT + text},
        ],
        json_mode=True,
        web_search=True,
    )

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # Fallback: try to extract the JSON object from the response text.
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            result = json.loads(content[start:end])
        else:
            raise ValueError("Model tidak mengembalikan JSON yang valid")

    return result


SUMMARY_PROMPT = """Kamu adalah editor berita Indonesia. Buatkan ringkasan singkat 
(maksimal 2 kalimat) dalam Bahasa Indonesia untuk artikel berita berikut. 
Ringkasan harus informatif dan netral.

Judul: {title}
Sumber: {source}

Berikan hanya ringkasan tanpa tambahan apapun."""


async def summarize_news(title: str, source: str) -> str:
    """Generate a short summary for a news article."""
    content = await _chat_completion(
        messages=[
            {
                "role": "user",
                "content": SUMMARY_PROMPT.format(title=title, source=source),
            },
        ],
        temperature=0.4,
    )

    return content.strip()
