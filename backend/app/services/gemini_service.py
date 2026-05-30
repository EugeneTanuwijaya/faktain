import json
import re
import asyncio
from datetime import datetime, timezone, timedelta
import httpx

from app.config import settings

# Google Gemini Developer API (REST). We call it directly with httpx so we
# don't need the google-generativeai SDK. Grounding with Google Search lets the
# model verify claims against live web content (free up to 5k req/month).
#
# Endpoint: {base}/models/{model}:generateContent?key={API_KEY}

# Relax safety filters: this app analyzes news/hoaxes that often touch
# political or sensitive topics. With default filters Gemini may refuse to
# analyze them. BLOCK_ONLY_HIGH keeps egregious content blocked without
# killing legitimate fact-checking.
_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
]


def _endpoint(model: str) -> str:
    base = settings.GEMINI_BASE_URL.rstrip("/")
    return f"{base}/models/{model}:generateContent"


def _extract_text(data: dict) -> str | None:
    """Concatenate all text parts from the first candidate."""
    candidates = data.get("candidates")
    if not candidates:
        return None
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    texts = [p["text"] for p in parts if isinstance(p, dict) and "text" in p]
    return "".join(texts) if texts else None


def _extract_grounding_sources(data: dict) -> list[dict]:
    """Pull {title, url} from the response's grounding metadata.

    These are the actual sources Google Search consulted, so they're more
    reliable than asking the model to transcribe long redirect URLs into JSON.
    """
    candidates = data.get("candidates")
    if not candidates:
        return []
    meta = candidates[0].get("groundingMetadata", {})
    sources = []
    for chunk in meta.get("groundingChunks", []):
        web = chunk.get("web", {})
        uri = web.get("uri")
        if uri:
            sources.append(
                {
                    "title": web.get("title", "") or uri,
                    "url": uri,
                    "credibility": "NETRAL",
                }
            )
    return sources


async def _resolve_one(client: httpx.AsyncClient, source: dict) -> dict | None:
    """Resolve a single grounding redirect URL to its final destination.

    Returns the source with a real URL, or None if it fails (e.g. expired/404)
    so dead links are dropped instead of shown to the user.
    """
    url = source.get("url", "")
    # Only redirect-style grounding URLs need resolving; pass others through.
    if "grounding-api-redirect" not in url:
        return source
    try:
        resp = await client.get(
            url,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AntiHoax/1.0)"},
        )
    except httpx.HTTPError:
        return None
    if resp.status_code >= 400:
        return None
    final = str(resp.url)
    if not final or "grounding-api-redirect" in final:
        return None
    return {**source, "url": final}


async def _resolve_sources(sources: list[dict]) -> list[dict]:
    """Resolve all grounding redirect URLs concurrently, dropping dead links."""
    if not sources:
        return sources
    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await asyncio.gather(
            *(_resolve_one(client, s) for s in sources),
            return_exceptions=True,
        )
    resolved = [r for r in results if isinstance(r, dict)]
    # If resolution failed for everything (e.g. network blocked), fall back to
    # the original list so the user still sees something.
    return resolved or sources


def _retry_delay_seconds(resp: httpx.Response) -> float | None:
    """Extract how long to wait before retrying a 429 response.

    Gemini reports the delay in two places. We prefer the structured
    RetryInfo detail (e.g. {"@type": ".../RetryInfo", "retryDelay": "30s"}),
    then fall back to parsing "retry in 30.5s" from the message text, then to
    the standard Retry-After header.
    """
    # 1. Structured RetryInfo in the error details.
    try:
        details = resp.json().get("error", {}).get("details", [])
        for d in details:
            if d.get("@type", "").endswith("RetryInfo") and d.get("retryDelay"):
                return float(str(d["retryDelay"]).rstrip("s"))
    except Exception:
        pass

    # 2. "Please retry in 30.56s" inside the message text.
    try:
        msg = resp.json().get("error", {}).get("message", "")
        m = re.search(r"retry in\s+([\d.]+)s", msg, re.IGNORECASE)
        if m:
            return float(m.group(1))
    except Exception:
        pass

    # 3. Standard Retry-After header (seconds).
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass

    return None


async def _post_with_retry(
    client: httpx.AsyncClient, payload: dict
) -> httpx.Response:
    """POST to Gemini, retrying transient 429s using the server-provided delay.

    Retries only on 429 (rate limit). The wait is capped by
    GEMINI_MAX_RETRY_WAIT so a long daily-quota backoff doesn't hang the
    request; in that case we return the 429 and let the caller surface it.
    """
    url = _endpoint(settings.GEMINI_MODEL)
    params = {"key": settings.GEMINI_API_KEY}
    headers = {"Content-Type": "application/json"}

    resp = await client.post(url, params=params, headers=headers, json=payload)

    for _ in range(settings.GEMINI_MAX_RETRIES):
        if resp.status_code != 429:
            return resp

        delay = _retry_delay_seconds(resp)
        # No usable delay, or it exceeds what we're willing to wait -> give up.
        if delay is None or delay > settings.GEMINI_MAX_RETRY_WAIT:
            return resp

        # Add a small buffer so we retry just after the window resets.
        await asyncio.sleep(delay + 0.5)
        resp = await client.post(url, params=params, headers=headers, json=payload)

    return resp


async def _generate(
    prompt: str,
    *,
    grounding: bool = False,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    json_response: bool = False,
) -> tuple[str, list[dict]]:
    """Call Gemini generateContent and return (text, grounding_sources).

    Note: Gemini does not allow forcing ``responseMimeType: application/json``
    together with the Google Search tool, so when grounding is on we rely on
    the prompt + lenient parser to recover JSON instead.

    ``grounding_sources`` is a list of {title, url} extracted from the
    response's grounding metadata (empty when grounding is off).
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY belum diset. Tambahkan API key Google AI Studio "
            "(diawali 'AIza') di backend/.env"
        )

    generation_config: dict = {
        "temperature": temperature,
        "maxOutputTokens": max_tokens or settings.GEMINI_MAX_TOKENS,
        # Limit internal "thinking" so the token budget goes to real output.
        "thinkingConfig": {"thinkingBudget": settings.GEMINI_THINKING_BUDGET},
    }
    # Structured JSON output only when NOT grounding (mutually exclusive).
    if json_response and not grounding:
        generation_config["responseMimeType"] = "application/json"

    payload: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
        "safetySettings": _SAFETY_SETTINGS,
    }
    if grounding:
        payload["tools"] = [{"google_search": {}}]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await _post_with_retry(client, payload)

    if resp.status_code != 200:
        try:
            err = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            err = resp.text
        if resp.status_code == 429:
            raise ValueError(
                "Kuota Gemini API terlampaui (429). Limit free tier sangat "
                "kecil (per menit & per hari). Tunggu sebentar lalu coba lagi, "
                "atau gunakan model dengan limit lebih besar / aktifkan billing. "
                f"Detail: {err}"
            )
        raise ValueError(f"Gemini API error {resp.status_code}: {err}")

    data = resp.json()

    # Surface prompt-level blocks with a clear message.
    feedback = data.get("promptFeedback", {})
    if feedback.get("blockReason"):
        raise ValueError(
            f"Permintaan diblokir oleh filter Gemini: {feedback['blockReason']}"
        )

    text = _extract_text(data)
    if not text:
        finish = (data.get("candidates") or [{}])[0].get("finishReason", "UNKNOWN")
        raise ValueError(
            f"Gemini tidak mengembalikan teks (finishReason: {finish})"
        )
    return text, _extract_grounding_sources(data)


def _repair_json(s: str) -> str:
    """Best-effort cleanup of common JSON defects from LLM output."""
    if not s:
        return s
    s = (
        s.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    s = re.sub(r"//[^\n\r]*", "", s)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


def _parse_json_lenient(content: str) -> dict | None:
    """Parse JSON from an LLM response, tolerating common formatting quirks."""
    if not content:
        return None

    candidates = [content]
    fenced = re.sub(r"```(?:json)?\s*", "", content).replace("```", "")
    candidates.append(fenced)
    start = fenced.find("{")
    end = fenced.rfind("}") + 1
    if start != -1 and end > start:
        candidates.append(fenced[start:end])

    for raw in candidates:
        for attempt in (raw, _repair_json(raw)):
            try:
                return json.loads(attempt)
            except (json.JSONDecodeError, TypeError):
                continue
    return None


ANALYSIS_PROMPT = """Kamu adalah fact-checker profesional yang berspesialisasi pada 
berita dan informasi di Indonesia.

## Konteks waktu (PENTING):
Hari ini tanggal {today}. Gunakan tanggal ini sebagai acuan "sekarang".
Pengetahuan internalmu mungkin sudah usang. Untuk fakta yang bisa berubah
(jabatan pejabat, presiden/menteri saat ini, kebijakan terbaru, harga, dll),
WAJIB mengandalkan hasil pencarian Google Search yang baru kamu dapatkan,
BUKAN ingatan/pengetahuan latihanmu. Jika hasil pencarian bertentangan dengan
ingatanmu, percayai hasil pencarian.

## LANGKAH WAJIB SEBELUM MENJAWAB:
Kamu HARUS melakukan pencarian Google Search terlebih dahulu untuk
memverifikasi klaim dalam teks. JANGAN menjawab hanya dari penalaran atau
ingatan. Lakukan minimal satu pencarian untuk klaim utama, baca hasilnya,
lalu baru susun analisis. Pencarian ini wajib walau kamu merasa sudah tahu
jawabannya.

## Tugasmu:
1. Analisis teks berita berikut untuk mendeteksi pola hoaks
2. PECAH klaim menjadi bagian-bagian SPESIFIK dan verifikasi tiap bagian
   secara terpisah, terutama: ANGKA/persentase, ATRIBUSI (siapa berkata/
   melakukan apa), WAKTU, dan KONTEKS. Sebuah pernyataan bisa "sebagian benar"
   namun tetap menyesatkan jika satu detailnya salah.
   Contoh: "Presiden menaikkan gaji guru 300%" — pisahkan menjadi (a) apakah
   benar ada kenaikan, (b) apakah benar 300%, (c) apakah benar untuk guru atau
   pihak lain. Verifikasi ketiganya.
3. Cari di internet untuk mengkonfirmasi atau membantah tiap bagian klaim
4. Bandingkan dengan sumber berita terpercaya Indonesia:
   Kompas, Tempo, CNN Indonesia, BBC Indonesia, Antara
5. PRIORITASKAN pengecekan ke situs fact-check: Turnbackhoax.id, Cekfakta.com,
   AFP Fact Check Indonesia, dan kanal cek fakta media besar. Jika ada artikel
   fact-check yang membahas klaim ini, jadikan rujukan utama.

## Aturan penilaian verdict (PENTING, bersikap kritis & konservatif):
- "KREDIBEL" HANYA jika SELURUH bagian klaim (angka, atribusi, waktu, konteks)
  terkonfirmasi benar oleh sumber terpercaya. Jangan beri KREDIBEL hanya karena
  sebagian klaim benar.
- Jika klaim sebagian benar tetapi ada detail yang salah, dilebih-lebihkan,
  salah atribusi, atau kehilangan konteks penting (misal kesalahan sebut/slip
  of the tongue yang kemudian diklarifikasi), gunakan "PERLU DICEK" atau
  "KEMUNGKINAN HOAKS" dan jelaskan bagian mana yang menyesatkan.
- Jika tidak menemukan sumber yang memadai, JANGAN menebak "KREDIBEL".
  Gunakan "PERLU DICEK".
- confidence_score harus mencerminkan kekuatan bukti, bukan keyakinan model.

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
  "suggestion": "<saran verifikasi lebih lanjut untuk user>"
}

PENTING:
- Keluarkan HANYA objek JSON, tanpa teks pembuka/penutup, tanpa markdown.
- Kamu TETAP WAJIB melakukan pencarian Google Search untuk menilai klaim
  (lihat langkah wajib di atas). Hanya saja, tidak perlu menyalin URL hasil
  pencarian ke dalam JSON — daftar sumber diambil otomatis dari metadata.
  Fokuskan isi JSON pada hasil analisis, bukan menyalin tautan.

## Teks yang dianalisis:
"""


async def analyze_text(text: str) -> dict:
    """Analyze text using Gemini with Google Search grounding."""
    # Inject the current date (WIB) so the model treats live search results as
    # "now" and doesn't fall back to a stale training-data view of the world.
    today = datetime.now(timezone(timedelta(hours=7))).strftime("%d %B %Y")
    prompt = ANALYSIS_PROMPT.replace("{today}", today) + text

    # The model occasionally skips the Google Search step and answers from
    # reasoning alone, yielding zero sources. When grounding is enabled we
    # retry once to coax it into actually searching before accepting a
    # source-less result.
    content = ""
    grounding_sources: list[dict] = []
    attempts = 2 if settings.GEMINI_GROUNDING else 1
    for attempt in range(attempts):
        content, grounding_sources = await _generate(
            prompt,
            grounding=settings.GEMINI_GROUNDING,
            json_response=True,
        )
        if grounding_sources or not settings.GEMINI_GROUNDING:
            break

    result = _parse_json_lenient(content)
    if result is None:
        raise ValueError("Gemini tidak mengembalikan JSON yang valid")

    # Sources come exclusively from Google Search grounding metadata (the model
    # is told not to emit them, keeping its JSON compact and free of truncation
    # from long redirect URLs). We resolve the temporary redirect URLs to their
    # real destinations so links don't 404.
    result["sources_found"] = await _resolve_sources(grounding_sources)

    return result


SUMMARY_PROMPT = """Kamu adalah editor berita Indonesia. Buatkan ringkasan singkat 
(maksimal 2 kalimat) dalam Bahasa Indonesia untuk artikel berita berikut. 
Ringkasan harus informatif dan netral.

Judul: {title}
Sumber: {source}

Berikan hanya ringkasan tanpa tambahan apapun."""


async def summarize_news(title: str, source: str) -> str:
    """Generate a short summary for a news article."""
    content, _ = await _generate(
        SUMMARY_PROMPT.format(title=title, source=source),
        grounding=False,
        temperature=0.4,
        max_tokens=256,
    )
    return content.strip()
