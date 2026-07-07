import json
import re
import asyncio
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import httpx

from app.config import settings

# LLM provider: OpenRouter (OpenAI-compatible Chat Completions API).
# Web search is provided by OpenRouter's "web" plugin; the underlying engine
# (Firecrawl) is selected in the OpenRouter dashboard, so no engine-specific
# code is needed here. Firecrawl returns full page content (clean markdown),
# letting the model reason over real articles rather than snippets.
#
# Endpoint: {base}/chat/completions

_CHAT_COMPLETIONS_URL = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"

_DEFAULT_HEADERS = {
    "Authorization": f"Bearer {settings.LLM_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": settings.FRONTEND_URL,
    "X-Title": "Anti-Hoax",
}

# Domains we consider trustworthy for credibility labeling. Sources from these
# are marked TERPERCAYA; everything else stays NETRAL.
_TRUSTED_DOMAINS = {
    "kompas.com",
    "tempo.co",
    "cnnindonesia.com",
    "bbc.com",
    "bbc.co.uk",
    "antaranews.com",
    "detik.com",
    "liputan6.com",
    "tribunnews.com",
    "kumparan.com",
    "republika.co.id",
    "suara.com",
    "katadata.co.id",
    "turnbackhoax.id",
    "cekfakta.com",
    "afp.com",
    "kominfo.go.id",
    "setkab.go.id",
}


# ---------------------------------------------------------------------------
# JSON parsing helpers (tolerant of the quirks free models emit)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Source extraction from OpenRouter web-search annotations
# ---------------------------------------------------------------------------
def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _credibility(url: str) -> str:
    return "TERPERCAYA" if _domain(url) in _TRUSTED_DOMAINS else "NETRAL"


def _extract_web_sources(message: dict) -> list[dict]:
    """Pull {title, url, credibility} from OpenRouter web-search annotations.

    OpenRouter attaches cited pages under message.annotations as items of
    type "url_citation". These are the real source URLs, so no redirect
    resolution is needed.
    """
    sources: list[dict] = []
    seen: set[str] = set()
    for ann in message.get("annotations") or []:
        if ann.get("type") != "url_citation":
            continue
        cite = ann.get("url_citation", {})
        url = cite.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append(
            {
                "title": cite.get("title") or _domain(url) or url,
                "url": url,
                "credibility": _credibility(url),
            }
        )
    return sources


# ---------------------------------------------------------------------------
# OpenRouter chat completion with retry + model fallback
# ---------------------------------------------------------------------------
def _build_payload(
    model: str,
    messages: list[dict],
    json_mode: bool,
    web_search: bool,
    temperature: float,
    max_tokens: int | None,
) -> dict:
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
    }
    # NOTE: forcing response_format=json_object together with the web plugin
    # makes the model skip searching (returns zero citations). So we only
    # request strict JSON mode when web search is OFF; when search is ON we
    # rely on the prompt + lenient parser to recover the JSON.
    if json_mode and not (web_search and settings.LLM_WEB_SEARCH):
        payload["response_format"] = {"type": "json_object"}
    if web_search and settings.LLM_WEB_SEARCH:
        # OpenRouter "web" plugin. Engine is configurable (firecrawl=free but
        # needs dashboard setup; exa=$0.005/req but reliable).
        plugin: dict = {"id": "web", "max_results": settings.LLM_WEB_MAX_RESULTS}
        if settings.LLM_WEB_ENGINE:
            plugin["engine"] = settings.LLM_WEB_ENGINE
        payload["plugins"] = [plugin]
    return payload


def _safe_response_json(resp: httpx.Response) -> dict | None:
    """Parse a 200 response body into JSON, tolerating OpenRouter quirks.

    OpenRouter sometimes prefixes the body with keep-alive comment lines
    (": OPENROUTER PROCESSING") or returns SSE-style "data: {...}" lines even
    for non-streaming requests. A plain resp.json() then raises
    "Expecting value: line N column 1". We strip those and recover the JSON.
    """
    try:
        return resp.json()
    except Exception:
        pass

    text = resp.text or ""
    # Collect "data: {...}" payload lines (SSE-style), ignoring comments (": ..").
    data_chunks = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("data:"):
            payload = s[len("data:"):].strip()
            if payload and payload != "[DONE]":
                data_chunks.append(payload)
    for chunk in reversed(data_chunks):  # last full object is usually complete
        try:
            return json.loads(chunk)
        except Exception:
            continue

    # Last resort: slice the outermost JSON object from the raw text.
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            return None
    return None


async def _chat_completion(
    messages: list[dict],
    *,
    json_mode: bool = False,
    web_search: bool = False,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    require_json: bool = False,
) -> tuple[str, list[dict]]:
    """Call OpenRouter and return (content, web_sources).

    Retries transient 429s with backoff and falls back to alternate models.
    Empty/None content (or non-JSON when ``require_json``) is also treated as
    a retryable failure, since free models occasionally return junk.
    """
    if not settings.LLM_API_KEY:
        raise ValueError(
            "LLM_API_KEY belum diset. Tambahkan API key OpenRouter di backend/.env"
        )

    models = [settings.LLM_MODEL] + [
        m for m in settings.LLM_FALLBACK_MODELS if m != settings.LLM_MODEL
    ]
    last_error = "tidak diketahui"

    async with httpx.AsyncClient(timeout=120.0) as client:
        for model in models:
            payload = _build_payload(
                model, messages, json_mode, web_search, temperature, max_tokens
            )

            for attempt in range(settings.LLM_MAX_RETRIES):
                try:
                    resp = await client.post(
                        _CHAT_COMPLETIONS_URL,
                        headers=_DEFAULT_HEADERS,
                        json=payload,
                    )
                except httpx.HTTPError as e:
                    last_error = f"koneksi gagal: {e}"
                    if attempt < settings.LLM_MAX_RETRIES - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue

                if resp.status_code == 200:
                    data = _safe_response_json(resp)
                    if data is None:
                        # 200 but body wasn't valid JSON (e.g. OpenRouter
                        # keep-alive comment lines leaked in, or partial body).
                        last_error = "respons 200 tetapi body bukan JSON valid"
                        if attempt < settings.LLM_MAX_RETRIES - 1:
                            await asyncio.sleep(1)
                        continue
                    try:
                        message = data["choices"][0]["message"]
                        content = message.get("content")
                    except (KeyError, IndexError):
                        message, content = {}, None

                    if not content or (
                        require_json and _parse_json_lenient(content) is None
                    ):
                        last_error = (
                            f"model '{model}' mengembalikan respons kosong/non-JSON"
                        )
                        if attempt < settings.LLM_MAX_RETRIES - 1:
                            await asyncio.sleep(1)
                        continue

                    return content, _extract_web_sources(message)

                try:
                    body = resp.json()
                    err = body.get("error", {}).get("message", resp.text)
                except Exception:
                    err = resp.text
                last_error = f"{resp.status_code}: {err}"

                if resp.status_code != 429:
                    raise ValueError(f"LLM API error {last_error}")

                retry_after = resp.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else 2 ** attempt
                except ValueError:
                    delay = 2 ** attempt
                if attempt < settings.LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(min(delay, 15))

    raise ValueError(
        f"LLM API error {last_error}. Semua model (termasuk fallback) gagal "
        f"memberi respons valid. Coba lagi sebentar lagi."
    )


# ---------------------------------------------------------------------------
# Analysis prompt
# ---------------------------------------------------------------------------
ANALYSIS_PROMPT = """Kamu adalah fact-checker profesional yang berspesialisasi pada 
berita dan informasi di Indonesia.

## Konteks waktu (PENTING):
Hari ini tanggal {today}. Gunakan tanggal ini sebagai acuan "sekarang".

## ⚠️ INSTRUKSI WAJIB — BACA INI DULU:
Kamu akan diberikan HASIL PENCARIAN WEB yang berisi fakta terbaru dari internet.
WAJIB membaca dan menggunakan hasil pencarian tersebut sebagai bukti utama.
JANGAN PERNAH mengklaim "tidak dapat mengakses internet" atau "tidak memiliki
akses web" — hasil pencarian sudah disediakan untukmu di bagian bawah prompt ini.

Untuk fakta yang bisa berubah (jabatan pejabat, presiden/menteri saat ini,
kebijakan terbaru, harga, dll), WAJIB mengandalkan hasil pencarian web,
BUKAN ingatan/pengetahuan latihanmu. Jika hasil pencarian bertentangan dengan
ingatanmu, percayai hasil pencarian.

## Tugasmu:
1. BACA hasil pencarian web yang disediakan (jika ada)
2. Analisis teks berita untuk mendeteksi pola hoaks
3. PECAH klaim menjadi bagian-bagian SPESIFIK dan verifikasi tiap bagian
   secara terpisah, terutama: ANGKA/persentase, ATRIBUSI (siapa berkata/
   melakukan apa), WAKTU, dan KONTEKS. Sebuah pernyataan bisa "sebagian benar"
   namun tetap menyesatkan jika satu detailnya salah.
   Contoh: "Presiden menaikkan gaji guru 300%" — pisahkan menjadi (a) apakah
   benar ada kenaikan, (b) apakah benar 300%, (c) apakah benar untuk guru atau
   pihak lain. Verifikasi ketiganya.
4. Gunakan hasil pencarian untuk mengkonfirmasi atau membantah tiap bagian klaim
5. Bandingkan dengan sumber berita terpercaya Indonesia:
   Kompas, Tempo, CNN Indonesia, BBC Indonesia, Antara
6. PRIORITASKAN situs fact-check: Turnbackhoax.id, Cekfakta.com,
   AFP Fact Check Indonesia, dan kanal cek fakta media besar. Jika ada artikel
   fact-check yang membahas klaim ini, jadikan rujukan utama.

## ⚠️ ATURAN RUANG LINGKUP KLAIM (SANGAT PENTING):
Verifikasi HANYA klaim yang BENAR-BENAR dinyatakan user dalam teks (eksplisit
maupun implisit langsung). JANGAN mengarang klaim baru dari detail yang hanya
muncul di hasil pencarian web.
- Tandai klaim INTI (yang dinyatakan user) dengan "is_core": true.
- Detail tambahan dari hasil pencarian yang TIDAK disebut user (mis. nama
  pejabat, jumlah personel, kutipan spesifik) BOLEH dicantumkan sebagai
  konteks dengan "is_core": false — tetapi JANGAN jadikan dasar untuk
  menurunkan verdict. Detail periferal yang "tidak dapat diverifikasi" TIDAK
  membuat klaim inti user menjadi kurang kredibel.
- Hanya klaim INTI yang DIBANTAH yang boleh menurunkan kredibilitas berita.

## Klaim kabur / tanpa waktu:
- Jika klaim user tidak menyebut WAKTU spesifik, JANGAN diam-diam menganggapnya
  pasti merujuk peristiwa hari ini. Nyatakan asumsi waktumu secara eksplisit di
  "explanation" (mis. "diasumsikan merujuk peristiwa terbaru per {today}") dan
  cantumkan di "suggestion" agar user mempersempit rentang waktu bila perlu.
- Untuk kata kualitatif/subjektif ("besar", "banyak", "heboh"), jelaskan bahwa
  klaim semacam ini sulit diverifikasi secara objektif; jangan menurunkan skor
  hanya karena subjektivitas ini selama inti peristiwanya terkonfirmasi.

## Aturan penilaian verdict (PENTING, bersikap kritis & konservatif):
- "KREDIBEL" jika SELURUH bagian klaim INTI (angka, atribusi, waktu, konteks)
  yang dinyatakan user terkonfirmasi benar oleh sumber terpercaya. Detail
  periferal (is_core=false) yang tidak dapat diverifikasi TIDAK menghalangi
  verdict KREDIBEL selama klaim inti terkonfirmasi.
- Jika klaim INTI sebagian benar tetapi ada detail inti yang salah,
  dilebih-lebihkan, salah atribusi, atau kehilangan konteks penting (misal
  kesalahan sebut/slip of the tongue yang kemudian diklarifikasi), gunakan
  "PERLU DICEK" atau "KEMUNGKINAN HOAKS" dan jelaskan bagian mana yang
  menyesatkan.
- Jika tidak menemukan sumber yang memadai untuk klaim inti, JANGAN menebak
  "KREDIBEL". Gunakan "PERLU DICEK".

## Arti confidence_score (PENTING — ini SKOR KREDIBILITAS):
confidence_score adalah tingkat KREDIBILITAS berita pada skala 0-100:
- 0   = hampir pasti HOAKS / tidak benar
- 100 = hampir pasti KREDIBEL / benar
Jadi SEMAKIN TINGGI skor, semakin terpercaya beritanya. Skor HARUS selaras
dengan verdict:
- "KEMUNGKINAN HOAKS"  -> skor RENDAH (0-30)
- "PERLU DICEK"        -> skor MENENGAH (40-60)
- "KREDIBEL"           -> skor TINGGI (75-100)
JANGAN memberi skor tinggi untuk verdict HOAKS. Skor mencerminkan kredibilitas
berita, bukan keyakinanmu pada analisis.

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
  "confidence_score": <angka 0-100, skor KREDIBILITAS: 0=hoaks, 100=kredibel>,
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
      "explanation": "<penjelasan hasil verifikasi>",
      "is_core": <true jika klaim dinyatakan user, false jika konteks tambahan>
    }
  ],
  "suggestion": "<saran verifikasi lebih lanjut untuk user>"
}

PENTING:
- Keluarkan HANYA objek JSON, tanpa teks pembuka/penutup, tanpa markdown.
- Tidak perlu menyalin URL hasil pencarian ke dalam JSON; daftar sumber
  dikumpulkan otomatis. Fokuskan isi JSON pada hasil analisis.

"""


WEB_RESEARCH_PROMPT = """Cari berita terbaru di internet (hari ini {today}) dan
jawab dengan FAKTA SPESIFIK: benarkah hal berikut? {claim}

Format jawaban:
FAKTA: [sebutkan fakta sebenarnya: angka, siapa pelakunya, kapan, dan konteksnya]
KESIMPULAN: [BENAR / SEBAGIAN BENAR / SALAH / TIDAK ADA INFO]
KLARIFIKASI: [adakah bantahan atau klarifikasi resmi?]

Jawab singkat dalam Bahasa Indonesia berdasarkan sumber yang kamu temukan."""


async def _web_research(text: str, today: str) -> tuple[str, list[dict]]:
    """Step 1: run a search-friendly query to gather a factual brief + sources.

    A short, question-style prompt triggers the web plugin far more reliably
    than the long analysis prompt. Retries once if no sources come back.
    """
    claim = text.strip()
    if len(claim) > 500:
        claim = claim[:500]
    prompt = WEB_RESEARCH_PROMPT.format(today=today, claim=claim)

    brief, sources = "", []
    for _ in range(max(1, settings.LLM_MAX_RETRIES)):
        brief, sources = await _chat_completion(
            messages=[{"role": "user", "content": prompt}],
            web_search=True,
            temperature=0.3,
            max_tokens=800,
        )
        if sources:
            break
    return brief, sources


async def analyze_text(text: str) -> dict:
    """Analyze text using an OpenRouter model with live web search.

    Two-step design for reliability:
    1. A dedicated search call (question-form) reliably triggers the web plugin
       and returns real source citations + a short factual brief.
    2. An analysis call turns the brief + original text into the verdict JSON.
    Decoupling fixes the flaky behavior where the long analysis prompt alone
    often failed to trigger a search (zero sources).
    """
    today = datetime.now(timezone(timedelta(hours=7))).strftime("%d %B %Y")

    # --- Step 1: gather sources + factual brief via web search ---
    brief = ""
    sources: list[dict] = []
    if settings.LLM_WEB_SEARCH:
        brief, sources = await _web_research(text, today)

    # --- Step 2: analyze using the brief as grounding context ---
    prompt = ANALYSIS_PROMPT.replace("{today}", today)
    if brief:
        # Make the brief VERY explicit so the model cannot claim "no web access"
        prompt += (
            "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "## ⚠️ HASIL PENCARIAN WEB (WAJIB BACA & GUNAKAN SEBAGAI BUKTI UTAMA)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Hasil pencarian web di bawah ini adalah FAKTA TERBARU yang HARUS kamu\n"
            "gunakan untuk memverifikasi klaim. JANGAN mengabaikan atau mengklaim\n"
            "\"tidak ada akses web\" — hasil pencarian INI adalah akses webmu.\n\n"
            f"{brief}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    prompt += "## Teks yang dianalisis:\n" + text

    content, more_sources = await _chat_completion(
        messages=[{"role": "user", "content": prompt}],
        json_mode=True,
        web_search=False,  # already grounded by the brief from step 1
        require_json=True,
    )

    result = _parse_json_lenient(content)
    if result is None:
        raise ValueError("Model tidak mengembalikan JSON yang valid")

    # Prefer step-1 citations; fall back to any from step 2.
    result["sources_found"] = sources or more_sources

    _enforce_verdict_consistency(result)
    return result


def _normalize_claim_status(status: str) -> str:
    """Map model status variants to the canonical set.

    Free models emit variants like "BELUM TERVERIFIKASI", "TIDAK TERVERIFIKASI",
    or English equivalents. Collapse them into the three statuses the UI knows:
    TERKONFIRMASI | DIBANTAH | TIDAK DAPAT DIVERIFIKASI.
    """
    s = str(status or "").strip().upper()
    if not s:
        return "TIDAK DAPAT DIVERIFIKASI"
    # Debunked / false
    if any(k in s for k in ("DIBANTAH", "SALAH", "HOAKS", "HOAX", "FALSE", "KELIRU")):
        return "DIBANTAH"
    # Confirmed / true
    if any(k in s for k in ("TERKONFIRMASI", "KONFIRM", "BENAR", "TRUE", "CONFIRMED", "VALID")):
        return "TERKONFIRMASI"
    # Everything else (BELUM TERVERIFIKASI, TIDAK DAPAT DIVERIFIKASI, UNVERIFIED, ...)
    return "TIDAK DAPAT DIVERIFIKASI"


def _enforce_verdict_consistency(result: dict) -> None:
    """Keep verdict and confidence_score consistent.

    confidence_score is a CREDIBILITY score (0=hoax, 100=credible). Smaller
    models sometimes emit a verdict that contradicts the score (e.g. verdict
    KEMUNGKINAN HOAKS with score 95) or claims that contradict the verdict.
    We first normalize claim statuses, then fix the verdict against the CORE
    claims only (peripheral context must not drag down the score), then clamp
    the score into the band that matches the final verdict.
    """
    claims = result.get("verified_claims") or []

    # --- Normalize statuses + default is_core so the UI/logic see clean data ---
    for c in claims:
        if isinstance(c, dict):
            c["status"] = _normalize_claim_status(c.get("status", ""))
            if "is_core" not in c or not isinstance(c.get("is_core"), bool):
                c["is_core"] = True

    # Only CORE claims (those the user actually stated) drive the verdict.
    # If the model marked everything peripheral, fall back to all claims so we
    # don't lose signal entirely.
    core = [c for c in claims if isinstance(c, dict) and c.get("is_core")]
    judging = core or [c for c in claims if isinstance(c, dict)]
    statuses = [str(c.get("status", "")).upper() for c in judging]
    verdict = str(result.get("verdict", "")).upper()
    reasoning = str(result.get("reasoning", "")).lower()

    # --- DETECT HALLUCINATION: model claims "no web access" despite grounding ---
    # This is a critical bug where the model ignores the web search brief and
    # claims it cannot verify. When this happens, downgrade to PERLU DICEK but
    # flag the issue in reasoning.
    hallucination_phrases = [
        "tidak memiliki akses",
        "tidak dapat mengakses internet",
        "tidak ada akses web",
        "saya tidak dapat memverifikasi klaim ini karena tidak",
    ]
    if any(phrase in reasoning for phrase in hallucination_phrases):
        # Model ignored the web brief. Keep verdict conservative (PERLU DICEK)
        # but inject a note so we can diagnose this pattern.
        result["_hallucination_detected"] = True
        if verdict not in ["PERLU DICEK", "KEMUNGKINAN HOAKS"]:
            verdict = "PERLU DICEK"

    has_debunked = any("DIBANTAH" in s for s in statuses)
    all_confirmed = bool(statuses) and all("TERKONFIRMASI" in s for s in statuses)
    any_confirmed = any("TERKONFIRMASI" in s for s in statuses)

    # --- Step 1: reconcile the verdict with the CORE claim evidence ---
    # A debunked core claim always knocks the verdict down. But an unverifiable
    # core claim only downgrades KREDIBEL when NONE of the core claims are
    # confirmed — a fully-confirmed core set should stay KREDIBEL even if a
    # peripheral detail was unverifiable.
    if has_debunked and verdict == "KREDIBEL":
        verdict = "KEMUNGKINAN HOAKS"
    elif verdict == "KREDIBEL" and judging and not all_confirmed and not any_confirmed:
        verdict = "PERLU DICEK"
    result["verdict"] = verdict

    # --- Step 2: clamp the credibility score into the verdict's band ---
    # KEMUNGKINAN HOAKS -> 0-30, PERLU DICEK -> 40-60, KREDIBEL -> 75-100.
    bands = {
        "KEMUNGKINAN HOAKS": (0, 30),
        "PERLU DICEK": (40, 60),
        "KREDIBEL": (75, 100),
    }
    band = bands.get(verdict)
    if band is None:
        return
    low, high = band
    score = result.get("confidence_score")
    if not isinstance(score, (int, float)):
        # Missing/invalid score -> use the middle of the band.
        result["confidence_score"] = (low + high) // 2
        return
    # Pull an out-of-band score to the nearest edge of its verdict's band.
    result["confidence_score"] = int(max(low, min(high, score)))


# ---------------------------------------------------------------------------
# News summarization (no web search needed; summarize the scraped article)
# ---------------------------------------------------------------------------
SUMMARY_PROMPT = """Kamu adalah editor berita Indonesia. Buatkan ringkasan
artikel berita berikut dalam Bahasa Indonesia yang informatif, netral, dan
mudah dipahami.

## Aturan:
- Ringkas menjadi 3-4 kalimat yang menangkap inti berita (siapa, apa, kapan,
  di mana, mengapa).
- Gunakan HANYA informasi yang ada di dalam teks artikel. JANGAN menambah
  fakta, angka, atau opini dari luar teks.
- Netral dan tidak sensasional. Hilangkan bahasa clickbait.
- Keluarkan HANYA teks ringkasan, tanpa judul, label, atau markdown.

## Judul artikel:
{title}

## Isi artikel:
{content}
"""


async def summarize_article(title: str, content: str) -> str:
    """Summarize the actual scraped article text (no web search)."""
    trimmed = content[:8000]
    text, _ = await _chat_completion(
        messages=[
            {
                "role": "user",
                "content": SUMMARY_PROMPT.format(title=title, content=trimmed),
            }
        ],
        web_search=False,
        temperature=0.3,
        max_tokens=400,
    )
    return text.strip()
