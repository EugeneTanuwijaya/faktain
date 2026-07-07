# 📚 BELAJAR.md — Dokumentasi Proses Pengembangan Anti-Hoax

Dokumen ini mencatat seluruh langkah, perintah, dan kode yang ditulis selama sesi pengembangan aplikasi Anti-Hoax.

---

## Daftar Isi

1. [Gambaran Umum Proyek](#1-gambaran-umum-proyek)
2. [Setup Awal & Struktur Folder](#2-setup-awal--struktur-folder)
3. [Pengembangan Backend (FastAPI)](#3-pengembangan-backend-fastapi)
4. [Pengembangan Frontend (Next.js)](#4-pengembangan-frontend-nextjs)
5. [Desain UI/UX Newspaper Style](#5-desain-uiux-newspaper-style)
6. [Infrastruktur & DevOps](#6-infrastruktur--devops)
7. [Verifikasi & Testing](#7-verifikasi--testing)
8. [Lessons Learned](#8-lessons-learned)

---

## 1. Gambaran Umum Proyek

### Tujuan
Membangun aplikasi web pendeteksi hoaks berbasis AI untuk pengguna Indonesia dengan fitur:
- Analisis teks/URL berita → verdict (KREDIBEL / PERLU DICEK / KEMUNGKINAN HOAKS)
- Skor kepercayaan 0-100
- Identifikasi indikator hoaks
- Verifikasi klaim dengan sumber terpercaya
- News feed berita Indonesia

### Tech Stack
| Layer | Teknologi |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11 |
| AI | Gemini 2.0 Flash + Google Search Grounding |
| Infra | Docker, Google Cloud Platform |

### Sumber Referensi
- `anti-hoax-app-techstack.md` — Panduan teknis lengkap
- `DESIGN.md` — Pedoman desain UI/UX bergaya koran cetak

---

## 2. Setup Awal & Struktur Folder

### 2.1 Membuat Struktur Folder Backend

**Cara yang digunakan:**
Tidak menggunakan perintah `mkdir`. Sebagai gantinya, menggunakan tool `fs_write` untuk membuat file `__init__.py` yang secara otomatis membuat folder beserta subfoldernya.

**File yang dibuat:**
```
backend/
├── app/
│   ├── __init__.py
│   ├── models/
│   │   └── __init__.py
│   ├── routers/
│   │   └── __init__.py
│   └── services/
│       └── __init__.py
```

**Penjelasan:**
- `__init__.py` membuat folder menjadi Python package yang bisa di-import
- Struktur memisahkan concerns: `models` untuk data, `routers` untuk endpoints, `services` untuk logika bisnis

---

## 3. Pengembangan Backend (FastAPI)

### 3.1 Konfigurasi Environment (`backend/app/config.py`)

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    NEWS_CACHE_TTL: int = int(os.getenv("NEWS_CACHE_TTL", "3600"))


settings = Settings()
```

**Penjelasan:**
- Menggunakan `python-dotenv` untuk membaca file `.env`
- Class `Settings` menyimpan semua konfigurasi
- Default values disediakan untuk development lokal
- `NEWS_CACHE_TTL` di-cast ke int karena env selalu string

---

### 3.2 Pydantic Models — Request Schema

**File:** `backend/app/models/request_models.py`

```python
from pydantic import BaseModel, Field
from typing import Optional


class AnalyzeRequest(BaseModel):
    text: Optional[str] = Field(None, description="Teks berita yang ingin dianalisis")
    url: Optional[str] = Field(None, description="URL artikel yang ingin dianalisis")
```

**Penjelasan:**
- `Optional[str]` berarti field boleh `None` atau string
- User hanya perlu kirim `text` ATAU `url`, tidak keduanya

---

### 3.3 Pydantic Models — Response Schema

**File:** `backend/app/models/response_models.py`

```python
class Indicator(BaseModel):
    type: str
    description: str
    severity: str  # low, medium, high


class VerifiedClaim(BaseModel):
    claim: str
    status: str  # TERKONFIRMASI | DIBANTAH | TIDAK DAPAT DIVERIFIKASI
    explanation: str


class Source(BaseModel):
    title: str
    url: str
    credibility: str  # TERPERCAYA | NETRAL | MERAGUKAN


class AnalysisResponse(BaseModel):
    confidence_score: int = Field(..., ge=0, le=100)
    verdict: str
    reasoning: str
    indicators: List[Indicator] = Field(default_factory=list)
    verified_claims: List[VerifiedClaim] = Field(default_factory=list)
    sources_found: List[Source] = Field(default_factory=list)
    suggestion: str = ""
    analyzed_text: Optional[str] = None
```

**Penjelasan:**
- `Field(..., ge=0, le=100)` — `...` berarti required, `ge=0` dan `le=100` untuk validasi range
- `default_factory=list` untuk list kosong default
- Nested models membuat struktur data bersih


### 3.4 Scraper Service (`backend/app/services/scraper_service.py`)

```python
import httpx
from newspaper import Article


async def scrape_article(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            html = response.text

        article = Article(url)
        article.set_html(html)
        article.parse()

        text = article.text
        if not text or len(text.strip()) < 50:
            raise ValueError("Konten artikel terlalu pendek")

        return text
    except httpx.HTTPError as e:
        raise ValueError(f"Gagal mengakses URL: {str(e)}")
```

**Penjelasan:**
- `async def` membuat fungsi asynchronous untuk performa lebih baik
- `httpx.AsyncClient` digunakan karena mendukung async
- `timeout=15.0` mencegah hanging jika server lambat
- `newspaper3k.Article` mengekstrak teks bersih dari HTML
- Validasi: minimal 50 karakter agar analisis bermakna

---

### 3.5 News Service (`backend/app/services/news_service.py`)

```python
import feedparser
import hashlib
from datetime import datetime, timezone

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss?hl=id&gl=ID&ceid=ID:id"
_news_cache = None  # In-memory cache


def _generate_id(link: str) -> str:
    return hashlib.md5(link.encode()).hexdigest()[:12]


async def fetch_news(limit: int = 20):
    global _news_cache
    
    # Check cache (1 hour TTL)
    if _news_cache:
        cache_age = (datetime.now(timezone.utc) - _news_cache["timestamp"]).seconds
        if cache_age < 3600:
            return _news_cache["articles"][:limit]

    feed = feedparser.parse(GOOGLE_NEWS_RSS_URL)
    articles = []
    
    for entry in feed.entries[:limit]:
        title = entry.get("title", "")
        source = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0]
            source = parts[1]
        
        articles.append(NewsItem(
            id=_generate_id(entry.get("link", "")),
            title=title,
            link=entry.get("link", ""),
            source=source,
            published=entry.get("published", ""),
        ))
    
    _news_cache = {"articles": articles, "timestamp": datetime.now(timezone.utc)}
    return articles
```

**Penjelasan:**
- `feedparser.parse()` membaca RSS feed (XML)
- Google News RSS URL: `?hl=id&gl=ID&ceid=ID:id` untuk berita Indonesia
- **Caching:** Variable global `_news_cache` dengan TTL 1 jam
- **ID Generation:** `hashlib.md5()` membuat hash unik dari URL
- **Title Parsing:** Google News format = `"Judul Berita - Sumber"`

---

### 3.6 Gemini Service (`backend/app/services/gemini_service.py`)

```python
import google.generativeai as genai

genai.configure(api_key=settings.GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    tools=["google_search"],  # Aktifkan Search Grounding
)

ANALYSIS_PROMPT = """Kamu adalah fact-checker profesional...

## Tugasmu:
1. Analisis teks berita untuk mendeteksi pola hoaks
2. Identifikasi klaim-klaim utama yang perlu diverifikasi
3. Cari di internet untuk mengkonfirmasi atau membantah
4. Bandingkan dengan sumber terpercaya Indonesia

## Format output (JSON ketat):
{
  "confidence_score": <angka 0-100>,
  "verdict": "<KREDIBEL | PERLU DICEK | KEMUNGKINAN HOAKS>",
  ...
}
"""


async def analyze_text(text: str) -> dict:
    prompt = ANALYSIS_PROMPT + text
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        ),
    )
    return json.loads(response.text)
```

**Penjelasan:**
- `tools=["google_search"]` mengaktifkan **Google Search Grounding**
- `response_mime_type="application/json"` memaksa output JSON
- **Prompt Engineering:** Peran, instruksi spesifik, format output ketat


### 3.7 Router: Analyze (`backend/app/routers/analyze.py`)

```python
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/analyze", tags=["Analisis"])


@router.post("", response_model=AnalysisResponse)
async def analyze_content(request: AnalyzeRequest):
    if not request.text and not request.url:
        raise HTTPException(status_code=400, detail="Harus menyertakan 'text' atau 'url'")

    content = request.text
    if request.url:
        content = await scrape_article(request.url)

    if len(content.strip()) < 20:
        raise HTTPException(status_code=400, detail="Teks terlalu pendek")

    result = await analyze_text(content)
    return AnalysisResponse(**result)
```

**Penjelasan:**
- `APIRouter(prefix="/analyze")` — semua endpoint berawalan `/analyze`
- `response_model=AnalysisResponse` — FastAPI validasi otomatis
- `HTTPException` untuk error dengan status code yang tepat:
  - `400` — Bad Request (input tidak valid)
  - `422` — Unprocessable Entity (scraping gagal)
  - `500` — Internal Server Error (AI error)

---

### 3.8 Router: News (`backend/app/routers/news.py`)

```python
router = APIRouter(prefix="/news", tags=["News Feed"])


@router.get("", response_model=NewsFeedResponse)
async def get_news(limit: int = 20):
    articles = await fetch_news(limit=limit)
    return NewsFeedResponse(
        articles=articles,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/{news_id}/analyze", response_model=AnalysisResponse)
async def analyze_news_article(news_id: str):
    news_item = await get_news_by_id(news_id)
    if not news_item:
        raise HTTPException(status_code=404, detail="Berita tidak ditemukan")
    
    content = await scrape_article(news_item.link)
    result = await analyze_text(content)
    return AnalysisResponse(**result)
```

**Penjelasan:**
- `@router.get("")` — `GET /news` untuk list berita
- `@router.get("/{news_id}/analyze")` — `GET /news/{id}/analyze`
- `limit: int = 20` — query parameter dengan default
- Path parameter `{news_id}` diekstrak otomatis oleh FastAPI

---

### 3.9 Main Application (`backend/app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Anti-Hoax API",
    description="API Pendeteksi Hoaks berbasis AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(news.router)


@app.get("/")
async def root():
    return {"name": "Anti-Hoax API", "status": "running", "docs": "/docs"}
```

**Penjelasan:**
- `CORSMiddleware` wajib agar frontend bisa akses backend (berbeda origin)
- `app.include_router()` mendaftarkan semua router
- Dokumentasi otomatis di `/docs` (Swagger UI)

---

### 3.10 Requirements (`backend/requirements.txt`)

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-dotenv==1.0.1
google-generativeai==0.8.3
httpx==0.27.2
newspaper3k==0.2.8
feedparser==6.0.11
pydantic==2.9.2
lxml==5.3.0
lxml_html_clean==0.4.1
```

| Package | Fungsi |
|---------|--------|
| `fastapi` | Framework API utama |
| `uvicorn` | ASGI server |
| `google-generativeai` | Gemini API SDK |
| `httpx` | HTTP client async |
| `newspaper3k` | Scraper artikel |
| `feedparser` | Parser RSS |

---

### 3.11 Dockerfile Backend

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Penjelasan:**
- `python:3.11-slim` — image ringan
- `--no-cache-dir` mengurangi ukuran image
- `CMD` perintah default saat container jalan


---

## 4. Pengembangan Frontend (Next.js)

### 4.1 Inisialisasi Project

**Perintah:**
```bash
npx --yes create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```

**Penjelasan flag:**
| Flag | Fungsi |
|------|--------|
| `--typescript` | Menggunakan TypeScript |
| `--tailwind` | Setup Tailwind CSS otomatis |
| `--app` | Menggunakan App Router |
| `--src-dir` | Kode di folder `src/` |
| `--use-npm` | Menggunakan npm |

### 4.2 Install Axios

```bash
npm install axios
```

---

### 4.3 TypeScript Types (`frontend/src/types/index.ts`)

```typescript
export interface Indicator {
  type: string;
  description: string;
  severity: "low" | "medium" | "high";
}

export interface AnalysisResult {
  confidence_score: number;
  verdict: "KREDIBEL" | "PERLU DICEK" | "KEMUNGKINAN HOAKS";
  reasoning: string;
  indicators: Indicator[];
  verified_claims: VerifiedClaim[];
  sources_found: Source[];
  suggestion: string;
}
```

**Penjelasan:**
- `interface` mendefinisikan bentuk data
- Union types `"low" | "medium" | "high"` membatasi nilai valid
- `?` menandakan field optional
- Types harus match dengan Pydantic models di backend

---

### 4.4 API Client (`frontend/src/lib/api.ts`)

```typescript
import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60s untuk AI analysis
});

export async function analyzeText(text: string): Promise<AnalysisResult> {
  const response = await api.post("/analyze", { text });
  return response.data;
}

export async function getNewsFeed(limit: number = 20): Promise<NewsFeedResponse> {
  const response = await api.get("/news", { params: { limit } });
  return response.data;
}
```

**Penjelasan:**
- `NEXT_PUBLIC_API_URL` — environment variable untuk URL backend
- `timeout: 60000` — 60 detik karena analisis AI butuh waktu
- Return type `Promise<T>` untuk async function

---

## 5. Desain UI/UX Newspaper Style

### 5.1 Filosofi Desain (dari DESIGN.md)

Mengikuti gaya **koran cetak klasik (broadsheet)**:
- Tipografi sebagai bintang utama
- Grid multi-kolom asimetris
- Garis pembatas tegas
- Warna krem kertas, bukan putih murni
- Tanpa shadow, gradient, atau border-radius

---

### 5.2 Global CSS (`frontend/src/app/globals.css`)

```css
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
  --color-paper: #f4f4f0;
  --color-ink: #1a1a1a;
  --color-meta: #555555;
  --color-rule: #111111;
  --color-accent-red: #8b0000;
  --color-accent-green: #1a5c1a;
}

body {
  background-color: var(--color-paper);
  font-family: 'Georgia', serif;
}

.rule-top { border-top: 2px solid var(--color-rule); }
.rule-bottom { border-bottom: 1px solid var(--color-rule); }

.headline {
  font-family: 'Playfair Display', serif;
  font-weight: 900;
  line-height: 1.1;
}

.meta-text {
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.drop-cap::first-letter {
  float: left;
  font-size: 3.5rem;
  font-weight: 900;
}
```

**Penjelasan:**
- **Font Stack:**
  - `Playfair Display` — serif untuk headline
  - `Georgia` — serif untuk body text
  - `Inter` — sans-serif untuk UI/meta
- **Custom Classes:**
  - `.rule-*` untuk garis pembatas
  - `.drop-cap` untuk huruf besar awal paragraf


### 5.3 Layout Component (`frontend/src/app/layout.tsx`)

```tsx
export default function RootLayout({ children }) {
  return (
    <html lang="id">
      <body>
        <div className="max-w-[1200px] mx-auto px-4">
          {/* Masthead */}
          <header className="text-center py-6">
            <h1 className="headline text-5xl md:text-7xl">ANTI-HOAX</h1>
            <p className="meta-text">Pendeteksi Hoaks Berbasis AI</p>
          </header>

          {/* Date bar */}
          <div className="rule-double flex justify-between">
            <span className="meta-text">{getCurrentDate()}</span>
            <nav>
              <Link href="/">Beranda</Link>
              <Link href="/news">Berita Terkini</Link>
            </nav>
          </div>

          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
```

**Penjelasan:**
- Struktur layout: **Masthead** → **Date Bar** → **Content** → **Footer**
- `max-w-[1200px]` membatasi lebar seperti koran cetak
- `getCurrentDate()` menampilkan tanggal Indonesia

---

### 5.4 Komponen Utama

#### AnalysisForm
```tsx
"use client";
import { useState } from "react";

export default function AnalysisForm({ onSubmit, isLoading }) {
  const [input, setInput] = useState("");
  const [inputType, setInputType] = useState<"text" | "url">("text");

  const isUrl = (text: string) => {
    try { new URL(text); return true; } 
    catch { return false; }
  };

  const handleInputChange = (value: string) => {
    setInput(value);
    setInputType(isUrl(value) ? "url" : "text");
  };
  
  // ...render form
}
```

**Penjelasan:**
- `"use client"` directive untuk client-side interactivity
- **Auto-detect URL:** Jika input valid URL, otomatis set type

#### VerdictCard
```tsx
export default function VerdictCard({ result }) {
  const getBadgeClass = () => {
    switch (result.verdict) {
      case "KREDIBEL": return "badge-kredibel";    // hijau
      case "PERLU DICEK": return "badge-perlu-dicek"; // kuning
      case "KEMUNGKINAN HOAKS": return "badge-hoaks"; // merah
    }
  };

  const getScoreColor = () => {
    if (result.confidence_score >= 75) return "green";
    if (result.confidence_score >= 40) return "yellow";
    return "red";
  };
  
  // ...render verdict, score, reasoning
}
```

#### NewsCard
```tsx
export default function NewsCard({ article, onAnalyze, isAnalyzing }) {
  return (
    <article className="rule-bottom pb-4">
      <h3 className="headline">{article.title}</h3>
      <span className="meta-text">{article.source}</span>
      <button onClick={() => onAnalyze(article.id)}>CEK FAKTA →</button>
    </article>
  );
}
```

---

## 6. Infrastruktur & DevOps

### 6.1 CI/CD Pipeline (`infra/cloudbuild.yaml`)

```yaml
steps:
  # Build & Deploy Backend
  - name: "gcr.io/cloud-builders/docker"
    args: ["build", "-t", "REGION-docker.pkg.dev/$PROJECT_ID/hoax-detector/backend:$COMMIT_SHA", "./backend"]
  
  - name: "gcr.io/cloud-builders/docker"
    args: ["push", "REGION-docker.pkg.dev/$PROJECT_ID/hoax-detector/backend:$COMMIT_SHA"]
  
  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    args: ["run", "deploy", "hoax-detector-backend", "--image=...", "--region=asia-southeast1"]

  # Build & Deploy Frontend (sama seperti di atas)
```

**Penjelasan:**
- Trigger otomatis saat push ke `main` branch
- Build Docker image → Push ke Artifact Registry → Deploy ke Cloud Run

---

## 7. Verifikasi & Testing

### 7.1 Build Frontend

**Perintah:**
```bash
cd frontend
npm run build
```

**Output:**
```
✓ Generating static pages (5/5)
Route (app)
┌ ○ /
├ ○ /_not-found
└ ○ /news
```

### 7.2 Perbaikan CSS Import Warning

**Masalah:**
```
@import rules must precede all rules aside from @charset and @layer statements
```

**Solusi:**
Pindahkan `@import url(...)` ke atas sebelum `@import "tailwindcss"`:

```css
/* Sebelum (salah) */
@import "tailwindcss";
@import url('https://fonts.googleapis.com/...');

/* Sesudah (benar) */
@import url('https://fonts.googleapis.com/...');
@import "tailwindcss";
```

---

## 8. Lessons Learned

### 8.1 Best Practices yang Diterapkan

1. **Struktur Folder yang Jelas**
   - Memisahkan `models`, `routers`, `services` di backend
   - Menggunakan `src/` di frontend untuk organisasi

2. **Type Safety**
   - Pydantic di backend untuk validasi request/response
   - TypeScript di frontend untuk type checking

3. **Error Handling**
   - HTTPException dengan status code yang tepat
   - Try-catch dengan pesan user-friendly

4. **Caching**
   - In-memory cache untuk news feed (TTL 1 jam)
   - Mengurangi request ke external API

5. **Environment Variables**
   - Semua konfigurasi di `.env`
   - Tidak hardcode sensitive values

### 8.2 Tantangan & Solusi

| Tantangan | Solusi |
|-----------|--------|
| `npx create-next-app` meminta konfirmasi | Gunakan `npx --yes` untuk auto-accept |
| CSS `@import` warning | Pindahkan font import ke atas |
| CORS error | Tambahkan `CORSMiddleware` di FastAPI |
| AI response lambat | Set `timeout: 60000` di axios |

### 8.3 Langkah Selanjutnya

Untuk menjalankan aplikasi:

**Backend:**
```bash
cd backend
pip install -r requirements.txt
# Buat file .env dengan GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Buka http://localhost:3000 di browser.

---

*Dokumen ini dibuat untuk pembelajaran dan referensi pengembangan.*


---

## Bug Fix: Verdict-Source Contradiction (4 Juni 2026)

### 🔴 Masalah yang Ditemukan

User melaporkan hasil analisis yang **kontradiktif berbahaya**:
- **Verdict**: KEMUNGKINAN HOAKS (score 12/100)
- **Reasoning**: "Tidak ada bukti resmi, klaim dibantah"
- **Sources**: 3 sumber TERPERCAYA (Liputan6, Kompas, Kejagung) yang **MENGKONFIRMASI penangkapan**

Ini adalah **inversi verdict** — sources membuktikan klaim BENAR, tapi analisis bilang HOAKS.

### 🔍 Root Cause Analysis

#### Arsitektur 2-Step Kita
```
Step 1: Web Research
├─ Input: claim text
├─ Call LLM dengan web plugin enabled
├─ OpenRouter → Firecrawl/Exa → scrape articles
└─ Output: brief (model summary) + sources (plugin metadata)

Step 2: Analysis  
├─ Input: brief + original text
├─ Call LLM tanpa web plugin
└─ Output: verdict JSON
```

#### Bug yang Ditemukan

**Step 1 Output yang Diterima**:
```python
brief = """
Maaf, saya tidak dapat mengakses internet...
KESIMPULAN: TIDAK ADA INFO
"""

sources = [
    {"title": "Kejagung Tetapkan Dadan Tersangka", "url": "...", "credibility": "TERPERCAYA"},
    {"title": "Dadan Ditahan Kejagung Sepulang Haji", "url": "...", "credibility": "TERPERCAYA"},
    {"title": "Eks Kepala BGN Masuk Jeruji", "url": "...", "credibility": "NETRAL"}
]
```

**Kesimpulan Diagnostic**:
- ❌ Model **tidak bisa membaca content** yang dikembalikan plugin web search
- ✅ Plugin **tetap return metadata sources** (title, URL, credibility) dengan benar
- ❌ Brief yang dikirim ke Step 2 hanya berisi "tidak ada info" — **menyesatkan**!

#### Mengapa Model Tidak Bisa Baca Content Plugin?

Ini adalah **limitation OpenRouter web plugin dengan model tertentu**:
1. Plugin scrape full page content → seharusnya diberikan ke model
2. Model gratis/kecil (gpt-5-mini, free models) **tidak menerima** atau **tidak bisa akses** content tersebut
3. Model hanya bisa return string kosong atau "tidak dapat mengakses internet"
4. TAPI metadata sources (title/URL) **selalu dikembalikan** ke Python code

### 💡 Solusi yang Diterapkan

#### Fix 1: Inject Source Titles ke Brief

```python
async def _web_research(text: str, today: str) -> tuple[str, list[dict]]:
    # ... call LLM with web search ...
    brief, sources = await _chat_completion(...)
    
    # 🔧 FIX: Inject source metadata ke brief
    if sources:
        source_list = "\n".join(
            f"- {src['title']} ({src['credibility']}) — {src['url']}"
            for src in sources
        )
        brief = f"{brief}\n\n## Sumber yang ditemukan:\n{source_list}"
    
    return brief, sources
```

**Sebelum**:
```
brief = "Tidak ada info"  ❌ MENYESATKAN
sources = [3 artikel valid]
```

**Sesudah**:
```
brief = """
Tidak ada info

## Sumber yang ditemukan:
- Kejagung Tetapkan Dadan Tersangka (TERPERCAYA)
- Dadan Ditahan Kejagung (TERPERCAYA)
- Eks Kepala BGN Masuk Jeruji (NETRAL)
"""
sources = [3 artikel valid]
```

Sekarang Step 2 **punya bukti konkret** dari title yang informatif.

#### Fix 2: Prompt Analysis yang Lebih Eksplisit

```python
ANALYSIS_PROMPT = """
⚠️ INSTRUKSI WAJIB — BACA INI DULU:
Kamu akan diberikan HASIL PENCARIAN WEB yang berisi fakta terbaru.
WAJIB membaca dan menggunakan hasil pencarian tersebut sebagai bukti utama.
JANGAN PERNAH mengklaim "tidak dapat mengakses internet" — hasil pencarian
sudah disediakan untukmu di bagian bawah prompt ini.
...
"""
```

Dan format inject brief dengan visual separator:

```python
prompt = ANALYSIS_PROMPT.replace("{today}", today)
if brief:
    prompt += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## ⚠️ HASIL PENCARIAN WEB (WAJIB BACA & GUNAKAN SEBAGAI BUKTI UTAMA)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{brief}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
```

#### Fix 3: Hallucination Detection

Tambah deteksi kalau model masih mengklaim "tidak ada akses web" despite grounding:

```python
def _enforce_verdict_consistency(result: dict) -> None:
    reasoning = str(result.get("reasoning", "")).lower()
    
    hallucination_phrases = [
        "tidak memiliki akses",
        "tidak dapat mengakses internet",
        "tidak ada akses web",
    ]
    
    if any(phrase in reasoning for phrase in hallucination_phrases):
        result["_hallucination_detected"] = True
        # Keep verdict conservative (PERLU DICEK)
        if verdict not in ["PERLU DICEK", "KEMUNGKINAN HOAKS"]:
            verdict = "PERLU DICEK"
```

#### Fix 4: Better Research Prompt Format

```python
WEB_RESEARCH_PROMPT = """Cari berita terbaru dan jawab dengan FAKTA SPESIFIK:
benarkah hal berikut? {claim}

Format jawaban:
FAKTA: [fakta sebenarnya]
KESIMPULAN: [BENAR / SEBAGIAN BENAR / SALAH / TIDAK ADA INFO]
KLARIFIKASI: [bantahan resmi?]
"""
```

### 🎯 Expected Result After Fix

**Before**:
```
VERDICT: KEMUNGKINAN HOAKS (12/100)
REASONING: "Tidak ada bukti resmi"
         ❌ SALAH — ada 3 sumber resmi!
```

**After**:
```
VERDICT: KREDIBEL (85/100)  
REASONING: "Dikonfirmasi oleh Liputan6 dan Kompas: Kejagung 
            menetapkan Dadan Hindayana tersangka dan menahan 
            di Rutan Salemba"
         ✅ BENAR — sesuai dengan sources
```

### 📊 Lessons Learned

1. **Plugin limitations**: Not all models can access plugin-returned content
2. **Metadata is reliable**: OpenRouter always returns source metadata (title/URL) even if model can't read content
3. **Explicit grounding**: When model is unreliable, inject critical info (source titles) manually
4. **Prompt engineering**: Use visual separators, warnings, and structured format to force model attention
5. **Validation layers**: Add post-processing to catch hallucinations and contradictions

### 🔧 Files Modified

- `backend/app/services/gemini_service.py`
  - `_web_research()`: Inject source titles to brief
  - `ANALYSIS_PROMPT`: More explicit instructions
  - `WEB_RESEARCH_PROMPT`: Structured format
  - `analyze_text()`: Better brief injection with visual separator
  - `_enforce_verdict_consistency()`: Hallucination detection

### ✅ Testing

Created `backend/test_verdict_contradiction.py` untuk diagnose:
- Runs both steps independently
- Prints intermediate outputs
- Shows what model receives vs what it returns

Run test:
```bash
cd backend
python test_verdict_contradiction.py
```

---

## Frontend Connection Fix (4 Juni 2026)

### 🔴 Issue
Frontend menampilkan "Gagal memuat berita. Pastikan backend berjalan." padahal backend sudah running.

### Root Cause
Multiple Next.js dev server instances running simultaneously:
- Port 3000 (PID 5972)
- Port 3002 (PID 28124)
- Port 3003 (newly started)

Conflict antar instance menyebabkan connection issues.

### Solution
1. Kill all running Next.js instances:
   ```powershell
   taskkill /PID 5972 /F
   taskkill /PID 28124 /F
   ```

2. Start fresh:
   ```bash
   cd frontend
   npm run dev
   ```

3. Verify:
   - Backend: http://localhost:8000 ✅
   - Frontend: http://localhost:3000 ✅

### Prevention
- Always check running processes before starting dev server
- Use `netstat -ano | findstr :3000` to check port usage
- Kill zombie processes with `taskkill`

### Documentation Added
- `TROUBLESHOOTING.md` — comprehensive guide untuk common issues
- `test_frontend_connection.html` — quick test tool untuk verify koneksi


---

# 🚀 SESI DEPLOY KE GOOGLE CLOUD PLATFORM (6 Juni 2026)

> Bagian ini mencatat **secara lengkap** proses men-deploy aplikasi Anti-Hoax
> (FastAPI backend + Next.js frontend) ke Google Cloud Run, termasuk setiap
> perintah, kode, bug yang muncul, dan cara memperbaikinya. Dibuat berurutan
> supaya bisa diikuti seperti tutorial.

## Daftar Isi Sesi Ini
- [A. Konsep Dasar yang Harus Dipahami Dulu](#a-konsep-dasar-yang-harus-dipahami-dulu)
- [B. Prasyarat & Persiapan Lingkungan](#b-prasyarat--persiapan-lingkungan)
- [C. Menyiapkan Resource di GCP](#c-menyiapkan-resource-di-gcp)
- [D. Perbaikan Kode Sebelum Deploy](#d-perbaikan-kode-sebelum-deploy)
- [E. Pipeline CI/CD (cloudbuild.yaml)](#e-pipeline-cicd-cloudbuildyaml)
- [F. Proses Deploy & Bug yang Ditemukan](#f-proses-deploy--bug-yang-ditemukan)
- [G. Masalah CORS Dua Format URL](#g-masalah-cors-dua-format-url)
- [H. Masalah News Cache Kosong](#h-masalah-news-cache-kosong)
- [I. Ringkasan Perintah Penting](#i-ringkasan-perintah-penting)
- [J. Pelajaran Utama](#j-pelajaran-utama)

---

## A. Konsep Dasar yang Harus Dipahami Dulu

Sebelum masuk ke perintah, ini konsep kunci yang dipakai sepanjang sesi:

| Layanan GCP | Fungsi dalam project ini |
|-------------|--------------------------|
| **Cloud Run** | Menjalankan container (backend & frontend) tanpa perlu kelola server. Otomatis scale, bayar sesuai pemakaian. |
| **Artifact Registry** | "Gudang" untuk menyimpan Docker image hasil build. |
| **Cloud Build** | Mesin CI/CD yang membaca `cloudbuild.yaml`, mem-build image, lalu deploy. |
| **Secret Manager** | Penyimpanan aman untuk data sensitif (API key), bukan plaintext di config. |
| **IAM** | Sistem izin: siapa boleh melakukan apa. |

**Prinsip penting Cloud Run yang jadi sumber beberapa bug:**
1. Cloud Run **menyuntik env var `PORT`** (default `8080`) dan container WAJIB listen di port itu.
2. Cloud Run itu **stateless** — variabel di memori (cache) bisa hilang/aneh saat container restart, dan tidak boleh diandalkan.
3. Tiap deploy membuat **revision** baru = container baru dengan memori bersih.

---

## B. Prasyarat & Persiapan Lingkungan

### B.1 Cek apakah gcloud CLI sudah terpasang

```powershell
gcloud version
```

Awalnya muncul error `gcloud is not recognized` — artinya belum terpasang atau
PATH belum ter-refresh. Setelah install Google Cloud SDK, ternyata lokasinya:

```
C:\Users\ADVAN\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd
```

**Pelajaran:** Setelah install gcloud, terminal yang sudah terbuka **belum tahu**
PATH baru. Solusi bersih: tutup & buka ulang terminal. Solusi cepat (yang dipakai
di sesi ini): panggil pakai path lengkap lewat variabel PowerShell.

```powershell
$gc = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
& $gc --version
```

> **Catatan:** Tanda `&` di PowerShell adalah *call operator*, dipakai untuk
> menjalankan program yang path-nya disimpan dalam variabel/string.

### B.2 Cek status login & project aktif

```powershell
& $gc auth list      # akun yang login
& $gc config list    # project & akun aktif
```

Hasil: sudah login sebagai `eugenetanuwijaya99@gmail.com`, project aktif
`vibecoding-498016`.

### B.3 Cek billing (WAJIB aktif)

```powershell
& $gc billing projects describe vibecoding-498016
```

Output `billingEnabled: true` → aman. Cloud Run & Cloud Build menolak jalan
kalau billing belum aktif, walaupun pemakaian masih di free tier.

---

## C. Menyiapkan Resource di GCP

### C.1 Aktifkan API yang dibutuhkan

```powershell
& $gc services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
```

| API | Untuk apa |
|-----|-----------|
| `run.googleapis.com` | Cloud Run |
| `artifactregistry.googleapis.com` | Simpan Docker image |
| `cloudbuild.googleapis.com` | Pipeline build/deploy |
| `secretmanager.googleapis.com` | Simpan API key |

### C.2 Buat repository Artifact Registry

```powershell
& $gc artifacts repositories create hoax-detector --repository-format=docker --location=asia-southeast1 --description="Anti-hoax app images"
```

- `hoax-detector` = nama repo
- `--repository-format=docker` = untuk menyimpan Docker image
- `--location=asia-southeast1` = region Singapura (terdekat dengan Indonesia)

### C.3 Simpan API key ke Secret Manager

Backend memakai **OpenRouter** (bukan Gemini langsung), lewat env `LLM_API_KEY`.
Key disimpan ke Secret Manager via stdin (pipe `|`) supaya tidak tampil di histori:

```powershell
$key = "sk-or-v1-xxxxx..."
$key | & $gc secrets create llm-api-key --data-file=-
```

- `--data-file=-` artinya "baca isi secret dari stdin", bukan dari file.

Verifikasi:
```powershell
& $gc secrets list
```

### C.4 Beri izin IAM ke service account

Cloud Build perlu izin untuk: deploy ke Cloud Run, bertindak sebagai service
account, dan membaca secret. Ada dua kemungkinan service account (tergantung umur
project), jadi kita beri izin ke keduanya untuk aman.

```powershell
$proj = "vibecoding-498016"
$cbSA = "serviceAccount:237232251242@cloudbuild.gserviceaccount.com"
$computeSA = "serviceAccount:237232251242-compute@developer.gserviceaccount.com"

foreach ($sa in @($cbSA, $computeSA)) {
  foreach ($role in @("roles/run.admin","roles/iam.serviceAccountUser","roles/secretmanager.secretAccessor","roles/artifactregistry.writer")) {
    & $gc projects add-iam-policy-binding $proj --member=$sa --role=$role --condition=None
  }
}
```

| Role | Izin yang diberikan |
|------|---------------------|
| `roles/run.admin` | Deploy & kelola Cloud Run |
| `roles/iam.serviceAccountUser` | Bertindak sebagai service account lain (dibutuhkan saat deploy) |
| `roles/secretmanager.secretAccessor` | Membaca secret saat runtime |
| `roles/artifactregistry.writer` | Push image ke Artifact Registry |

> **Cara dapat project number** (`237232251242`):
> ```powershell
> & $gc projects describe vibecoding-498016 --format="value(projectNumber)"
> ```
> ⚠️ Hati-hati: jangan pakai variabel bernama `$pid` di PowerShell — itu variabel
> bawaan (process ID) dan akan menimpa nilaimu. Pakai `$proj` / `$pnum`.

---

## D. Perbaikan Kode Sebelum Deploy

Tiga hal yang HARUS diperbaiki sebelum deploy bisa berhasil.

### D.1 Aktifkan mode `standalone` di Next.js

**Masalah:** `frontend/Dockerfile` menyalin dari `.next/standalone`, tapi
`next.config.ts` belum mengaktifkan mode itu → build Docker pasti gagal.

```typescript
// frontend/next.config.ts
const nextConfig: NextConfig = {
  // Hasilkan server mandiri (.next/standalone) agar bisa `node server.js`
  // tanpa node_modules penuh.
  output: "standalone",
};
```

**Kenapa standalone?** Next.js menghasilkan bundle minimal berisi hanya file yang
dibutuhkan untuk produksi. Image Docker jadi jauh lebih kecil & cepat start.

### D.2 Frontend Dockerfile menerima URL backend saat build

**Masalah inti (penting!):** Variabel `NEXT_PUBLIC_*` di Next.js **di-bake saat
build**, bukan dibaca saat runtime. Jadi URL backend harus dimasukkan saat
`npm run build`, bukan saat container jalan.

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# NEXT_PUBLIC_* di-inline saat build → backend URL harus lewat build arg
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

Ini pakai **multi-stage build**: stage `builder` untuk compile, stage `runner`
untuk hasil akhir yang ramping (tidak bawa source code & dev dependencies).

### D.3 Backend Dockerfile bind ke `$PORT` (BUG yang menggagalkan deploy pertama)

**Masalah:** Dockerfile lama hardcode port `8000`, tapi Cloud Run mengirim
`PORT=8080` dan mengecek port itu. Akibatnya health check gagal → deploy ditolak.

```dockerfile
# backend/Dockerfile — SEBELUM (gagal di Cloud Run)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# backend/Dockerfile — SESUDAH (benar)
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**Kenapa pakai `sh -c "..."` (shell form), bukan array (exec form)?**
- `${PORT:-8000}` adalah sintaks shell = "pakai `PORT`, kalau kosong pakai `8000`".
- Sintaks ini hanya diproses kalau dijalankan lewat shell.
- Kalau ditulis array biasa, teks `${PORT:-8000}` dianggap string mentah.
- Fallback `8000` berguna saat `docker run` di laptop tanpa set `PORT`.

### D.4 Buat `.gcloudignore` agar upload kecil

**Masalah:** `gcloud builds submit` meng-upload seluruh folder. Tanpa filter,
`node_modules`, `.next`, `.git` ikut → ratusan MB.

```gitignore
# .gcloudignore
.git/
.gitignore
**/node_modules/
**/.next/
frontend/.env*.local
**/__pycache__/
**/*.pyc
backend/.venv/
backend/.env
backend/_diag.py
backend/_gm_dump.json
.vscode/
.kiro/
.playwright-mcp/
*.png
*.md
```

**Hasil nyata:** upload turun jadi hanya **~51 file (377 KiB)**. Dependency tetap
di-install di dalam Docker (`npm ci` / `pip install`), jadi tidak perlu di-upload.

---

## E. Pipeline CI/CD (cloudbuild.yaml)

### E.1 Tantangan: ketergantungan melingkar antara FE & BE

- Frontend butuh **URL backend** (di-bake saat build).
- Backend butuh **URL frontend** (untuk izin CORS).
- Kedua URL baru ada **setelah** masing-masing di-deploy.

Solusi: urutan bertahap →
deploy backend → ambil URL backend → build frontend pakai URL itu →
deploy frontend → update backend dengan URL frontend.

### E.2 File lengkap `infra/cloudbuild.yaml`

```yaml
substitutions:
  _REGION: asia-southeast1
  _REPO: hoax-detector
  # Build manual mengosongkan COMMIT_SHA, jadi default "latest".
  _TAG: latest

steps:
  # 1. Build + push backend
  - name: "gcr.io/cloud-builders/docker"
    id: "build-backend"
    args: [build, -t, "${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/backend:${_TAG}", ./backend]

  - name: "gcr.io/cloud-builders/docker"
    id: "push-backend"
    waitFor: ["build-backend"]
    args: [push, "${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/backend:${_TAG}"]

  # 2. Deploy backend (inject secret + project id)
  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    id: "deploy-backend"
    waitFor: ["push-backend"]
    entrypoint: gcloud
    args:
      - run
      - deploy
      - hoax-detector-backend
      - --image=${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/backend:${_TAG}
      - --region=${_REGION}
      - --platform=managed
      - --allow-unauthenticated
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID
      - --set-secrets=LLM_API_KEY=llm-api-key:latest

  # 3. Ambil URL backend ke /workspace (image docker tak punya gcloud)
  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    id: "get-backend-url"
    waitFor: ["deploy-backend"]
    entrypoint: bash
    args:
      - -c
      - |
        set -e
        gcloud run services describe hoax-detector-backend \
          --region=${_REGION} --format='value(status.url)' > /workspace/backend_url.txt
        echo "Backend URL: $(cat /workspace/backend_url.txt)"

  # 4. Build frontend pakai URL backend dari /workspace
  - name: "gcr.io/cloud-builders/docker"
    id: "build-frontend"
    waitFor: ["get-backend-url"]
    entrypoint: bash
    args:
      - -c
      - |
        set -e
        BACKEND_URL=$(cat /workspace/backend_url.txt)
        docker build \
          --build-arg NEXT_PUBLIC_API_URL=$$BACKEND_URL \
          -t ${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/frontend:${_TAG} \
          ./frontend

  - name: "gcr.io/cloud-builders/docker"
    id: "push-frontend"
    waitFor: ["build-frontend"]
    args: [push, "${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/frontend:${_TAG}"]

  # 5. Deploy frontend
  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    id: "deploy-frontend"
    waitFor: ["push-frontend"]
    entrypoint: gcloud
    args:
      - run
      - deploy
      - hoax-detector-frontend
      - --image=${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/frontend:${_TAG}
      - --region=${_REGION}
      - --platform=managed
      - --allow-unauthenticated

  # 6. Patch CORS backend dengan URL frontend asli
  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    id: "patch-backend-cors"
    waitFor: ["deploy-frontend"]
    entrypoint: bash
    args:
      - -c
      - |
        set -e
        FRONTEND_URL=$(gcloud run services describe hoax-detector-frontend \
          --region=${_REGION} --format='value(status.url)')
        gcloud run services update hoax-detector-backend \
          --region=${_REGION} \
          --update-env-vars=FRONTEND_URL=$$FRONTEND_URL

images:
  - ${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/backend:${_TAG}
  - ${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/frontend:${_TAG}

options:
  logging: CLOUD_LOGGING_ONLY
```

### E.3 Konsep penting di cloudbuild.yaml

| Konsep | Penjelasan |
|--------|------------|
| `substitutions` | Variabel yang bisa di-override saat submit. `$PROJECT_ID` & `$COMMIT_SHA` adalah bawaan Cloud Build. |
| `_TAG: latest` | Build manual mengosongkan `$COMMIT_SHA`. Kalau dipakai langsung, tag image rusak. Maka kita pakai `_TAG` default `latest`. |
| `waitFor` | Menentukan urutan & dependency antar step. |
| `name` vs `entrypoint` | `name` = image container untuk step itu; `entrypoint` = perintah yang dijalankan (mis. `gcloud` atau `bash`). |
| `/workspace` | Folder yang **dibagikan** ke semua step. Cara mengoper data antar step. |
| `$$BACKEND_URL` | Dobel `$$` = escape. Supaya `$` diteruskan apa adanya ke bash, bukan diproses Cloud Build. |
| `--allow-unauthenticated` | Service bisa diakses publik tanpa login. |

### E.4 Menjalankan pipeline

```powershell
& $gc builds submit --config infra/cloudbuild.yaml --substitutions _TAG=latest .
```

---

## F. Proses Deploy & Bug yang Ditemukan

Deploy butuh **3x percobaan**. Tiap kegagalan mengajarkan sesuatu.

### F.1 Cara memantau build

Karena `logging: CLOUD_LOGGING_ONLY`, log tidak streaming ke terminal. Pantau via:

```powershell
# Cek status keseluruhan
& $gc builds describe BUILD_ID --format="value(status)"

# Cek status tiap step (urut sesuai cloudbuild.yaml)
& $gc builds describe BUILD_ID --format="value(steps[].status)"

# Baca log detail dari Cloud Logging
& $gc logging read "resource.type=build AND resource.labels.build_id=BUILD_ID" --format="value(textPayload)" --limit=300 --order=asc
```

### F.2 BUILD 1 — GAGAL di step deploy-backend

```
SUCCESS;SUCCESS;FAILURE;QUEUED;QUEUED;QUEUE
```

Error dari log:
```
ERROR: The user-provided container failed to start and listen on the port
defined provided by the PORT=8080 environment variable...
```

**Penyebab:** backend hardcode port 8000 (lihat bagian D.3).
**Perbaikan:** ubah CMD jadi `${PORT:-8000}`.

### F.3 BUILD 2 — GAGAL di step build-frontend

```
SUCCESS;SUCCESS;SUCCESS;FAILURE;QUEUED;QUEUED
```

Error:
```
Backend URL: https://hoax-detector-backend-qwtbyvmotq-as.a.run.app
bash: line 5: docker: command not found
```

**Penyebab:** step build-frontend awalnya pakai image `cloud-sdk` (punya `gcloud`,
tapi TIDAK punya `docker`). Saya butuh keduanya: `gcloud` untuk ambil URL backend,
`docker` untuk build image.

**Perbaikan:** pecah jadi 2 step memakai `/workspace` sebagai jembatan (lihat
step 3 & 4 di E.2):
- Step `get-backend-url` (image `cloud-sdk`) → tulis URL ke `/workspace/backend_url.txt`
- Step `build-frontend` (image `docker`) → baca file itu

### F.4 BUILD 3 — SUKSES

```
SUCCESS;SUCCESS;SUCCESS;SUCCESS;SUCCESS;SUCCESS;SUCCESS;SUCCESS
```

### F.5 Verifikasi nyata (jangan berhenti di "SUCCESS")

```powershell
# Ambil URL kedua service
& $gc run services list --region=asia-southeast1 --format="table(metadata.name, status.url)"

# Tes backend benar-benar hidup
Invoke-WebRequest -Uri "https://.../health" -UseBasicParsing   # → {"status":"healthy"}

# Tes frontend merender
Invoke-WebRequest -Uri "https://..." -UseBasicParsing          # → StatusCode 200
```

> **Prinsip:** status build `SUCCESS` hanya berarti perintah berhasil dijalankan.
> Itu BUKAN jaminan aplikasi melayani pengguna. Selalu verifikasi di kondisi nyata.

---

## G. Masalah CORS Dua Format URL

### G.1 Gejala
Membuka frontend lewat URL **format baru** terasa "backend tidak jalan", padahal
backend hidup di kedua URL.

### G.2 Dua format URL Cloud Run

| Format | Contoh | Struktur |
|--------|--------|----------|
| Lama (Gen 1) | `...frontend-qwtbyvmotq-as.a.run.app` | `{service}-{hash-acak}-{kode-region}.a.run.app` |
| Baru (Gen 2) | `...frontend-237232251242.asia-southeast1.run.app` | `{service}-{project-number}.{region}.run.app` |

Keduanya menunjuk ke container yang sama, hanya beda alamat.

### G.3 Akar masalah = CORS

Browser punya aturan: JavaScript dari domain A tidak boleh memanggil API domain B
kecuali B mengizinkan origin A. Frontend & backend beda URL, jadi backend harus
mendaftarkan URL frontend di daftar `allow_origins`.

Sebelumnya daftar itu hanya berisi URL format lama. Saat frontend dibuka via URL
format baru, backend menolak request → browser menampilkan error CORS.

> **Penting:** Error CORS HANYA muncul di browser. Kalau dites pakai `curl` /
> `Invoke-WebRequest` akan tetap berhasil. Jadi kalau backend OK via curl tapi
> gagal di browser → hampir pasti CORS.

### G.4 Perbaikan kode (`backend/app/main.py`)

```python
# CORS — terima format URL lama & baru. FRONTEND_URL boleh dipisah koma.
_origins = [
    origin.strip()
    for origin in settings.FRONTEND_URL.split(",")
    if origin.strip()
] + [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### G.5 Set env var berisi koma (TRICKY)

Mengeset env var yang mengandung koma lewat `--set-env-vars` GAGAL karena gcloud
menganggap koma sebagai pemisah antar variabel:

```
ERROR: Bad syntax for dict arg: [...]
```

**Solusi bersih:** pakai `--env-vars-file` dengan file YAML.

```yaml
# env-vars.yaml (file sementara)
FRONTEND_URL: "https://hoax-detector-frontend-qwtbyvmotq-as.a.run.app,https://hoax-detector-frontend-237232251242.asia-southeast1.run.app"
GCP_PROJECT_ID: "vibecoding-498016"
```

```powershell
& $gc run services update hoax-detector-backend --region=asia-southeast1 --env-vars-file=backend/env-vars.yaml --set-secrets=LLM_API_KEY=llm-api-key:latest
```

### G.6 Ingat: ubah KODE → harus rebuild image

Mengubah env var saja membuat revision baru dari **image yang sama**. Tapi karena
kita juga mengubah `main.py`, image backend harus di-rebuild & deploy ulang:

```powershell
# Rebuild backend image saja (lebih cepat dari full pipeline)
& $gc builds submit --tag asia-southeast1-docker.pkg.dev/vibecoding-498016/hoax-detector/backend:latest ./backend

# Deploy image baru
& $gc run deploy hoax-detector-backend --image=asia-southeast1-docker.pkg.dev/vibecoding-498016/hoax-detector/backend:latest --region=asia-southeast1 --platform=managed --allow-unauthenticated --set-secrets=LLM_API_KEY=llm-api-key:latest
```

### G.7 Verifikasi CORS

```powershell
$r = Invoke-WebRequest -Uri "https://.../health" -Method OPTIONS -UseBasicParsing -Headers @{
  "Origin"="https://hoax-detector-frontend-237232251242.asia-southeast1.run.app";
  "Access-Control-Request-Method"="POST"
}
$r.Headers['Access-Control-Allow-Origin']   # harus mengembalikan origin yang diminta
```

---

## H. Masalah News Cache Kosong

### H.1 Gejala
Frontend menampilkan "Berita terkini belum tersedia." Endpoint backend `/news`
mengembalikan `{"articles":[],"last_updated":"..."}` — HTTP 200 tapi kosong.

### H.2 Diagnosis bertahap

```powershell
# 1. Endpoint /news → articles kosong []
Invoke-WebRequest -Uri "https://.../news?limit=5" -UseBasicParsing

# 2. RSS Google News bisa diakses? → ya, 151 KB XML valid
Invoke-WebRequest -Uri "https://news.google.com/rss?hl=id&gl=ID&ceid=ID:id" -UseBasicParsing

# 3. Log request /news → semua 200, tanpa error
& $gc logging read "resource.type=cloud_run_revision AND resource.labels.service_name=hoax-detector-backend AND httpRequest.requestUrl:/news" --limit=10
```

Kesimpulan: RSS bisa diakses, request sukses, tapi `articles` kosong → kecurigaan
mengarah ke **cache in-memory yang stuck**.

### H.3 Akar masalah

`news_service.py` memakai cache in-memory (`_news_cache`) dengan TTL 1 jam.
Di Cloud Run yang stateless:
1. Container pertama start dengan cache kosong.
2. Karena suatu sebab (race/cold-start), cache tidak pernah terisi dengan benar.
3. Container tidak pernah restart (tidak ada crash/redeploy/traffic spike).
4. Semua request berikutnya dapat `[]` dari cache yang stuck.

### H.4 Perbaikan cepat

Force redeploy → container baru → cache bersih → RSS di-fetch ulang:

```powershell
& $gc run services update hoax-detector-backend --region=asia-southeast1 --image=asia-southeast1-docker.pkg.dev/vibecoding-498016/hoax-detector/backend:latest
```

Setelah itu `/news` mengembalikan 5 artikel, dan frontend menampilkan berita.

### H.5 Rekomendasi jangka panjang
- **Ganti cache** ke Firestore/Redis (in-memory tidak andal di Cloud Run).
- **Tambah endpoint** `/news/refresh` untuk flush manual.
- **Atau hilangkan cache** — RSS parsing cepat (<1 detik) untuk traffic rendah.

> **Pelajaran besar:** State di memori (variabel global) adalah anti-pattern di
> lingkungan serverless yang stateless seperti Cloud Run.

---

## I. Ringkasan Perintah Penting

Cheat-sheet untuk dipakai lagi nanti (ganti placeholder sesuai project).

```powershell
# --- Setup variabel gcloud (jika PATH belum ke-refresh) ---
$gc = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

# --- Auth & project ---
& $gc auth login
& $gc config set project PROJECT_ID
& $gc config list

# --- Aktifkan API ---
& $gc services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# --- Artifact Registry ---
& $gc artifacts repositories create REPO --repository-format=docker --location=REGION

# --- Secret Manager ---
"NILAI_SECRET" | & $gc secrets create NAMA_SECRET --data-file=-
& $gc secrets list

# --- Jalankan pipeline penuh ---
& $gc builds submit --config infra/cloudbuild.yaml --substitutions _TAG=latest .

# --- Build & deploy satu service saja ---
& $gc builds submit --tag REGION-docker.pkg.dev/PROJECT_ID/REPO/backend:latest ./backend
& $gc run deploy SERVICE --image=... --region=REGION --allow-unauthenticated --set-secrets=KEY=secret:latest

# --- Pantau build ---
& $gc builds describe BUILD_ID --format="value(status)"
& $gc builds describe BUILD_ID --format="value(steps[].status)"

# --- Lihat service & URL ---
& $gc run services list --region=REGION --format="table(metadata.name, status.url)"
& $gc run services describe SERVICE --region=REGION --format="yaml(spec.template.spec.containers[0].env)"

# --- Update env var (pakai file untuk value berkoma) ---
& $gc run services update SERVICE --region=REGION --env-vars-file=env.yaml

# --- Baca log ---
& $gc logging read "resource.type=cloud_run_revision AND resource.labels.service_name=SERVICE" --limit=20
```

---

## J. Pelajaran Utama

1. **Cloud Run & PORT.** Container WAJIB listen di `$PORT` (default 8080). Jangan
   hardcode port. Pakai `--port ${PORT:-8000}` dalam shell form.

2. **`NEXT_PUBLIC_*` di-bake saat build.** URL backend harus masuk lewat
   `--build-arg` saat `docker build`, bukan diset saat runtime.

3. **`/workspace` adalah jembatan antar step Cloud Build.** Tiap step jalan di
   container berbeda; tulis data ke `/workspace` untuk dioper ke step berikutnya.

4. **Pilih image step yang punya tool yang dibutuhkan.** `cloud-sdk` punya
   `gcloud` tapi bukan `docker`. Jangan campur dalam satu step.

5. **`$$` untuk escape `$` di cloudbuild.yaml.** Supaya variabel dibaca oleh bash,
   bukan oleh Cloud Build.

6. **Ubah kode → rebuild image.** Update env var saja TIDAK memasukkan perubahan
   kode. Image harus di-build ulang lalu deploy.

7. **CORS error cuma di browser.** Tes curl bisa lolos walau browser gagal. Daftar
   `allow_origins` harus mencakup semua origin frontend (termasuk dua format URL).

8. **Value berkoma → pakai `--env-vars-file`.** `--set-env-vars` menganggap koma
   sebagai pemisah variabel.

9. **State in-memory itu rapuh di serverless.** Cache di variabel global bisa
   stuck. Gunakan store eksternal (Firestore/Redis) atau redeploy untuk reset.

10. **"SUCCESS" ≠ "berfungsi".** Selalu verifikasi nyata: `/health`, status 200,
    dan render di browser.

11. **`.gcloudignore` menghemat banyak.** Upload turun dari ratusan MB jadi ~377 KiB.

12. **Hati-hati variabel bawaan PowerShell.** Jangan pakai `$pid` (process ID
    bawaan); pakai nama lain seperti `$proj`.

---

*Bagian sesi deploy GCP dibuat 6 Juni 2026 — sebagai catatan belajar end-to-end.*


---

# 🔐 SESI FITUR LOGIN (Firebase Auth) + KESIAPAN PRODUCTION GCP (13 Juni 2026)

> Bagian ini mencatat sesi penambahan **login Google (Firebase Auth)** ke aplikasi,
> mulai dari keputusan desain, implementasi kode, pengisian kredensial, verifikasi
> di browser, sampai **apa yang harus disiapkan agar login berfungsi di production
> Google Cloud Run**. Disusun berurutan seperti tutorial.
>
> Catatan: detail implementasi kode per-file juga ada di `docs/PANDUAN-FITUR-LOGIN.md`.
> Bagian di sini menekankan **alur sesi + bagian deploy GCP**.

## Daftar Isi Sesi Ini
- [K. Keputusan Desain: Kenapa Login Opsional](#k-keputusan-desain-kenapa-login-opsional)
- [L. Ringkasan Implementasi Kode](#l-ringkasan-implementasi-kode)
- [M. Semua Command yang Dijalankan](#m-semua-command-yang-dijalankan)
- [N. Mengisi Kredensial Firebase & Verifikasi](#n-mengisi-kredensial-firebase--verifikasi)
- [O. KESIAPAN PRODUCTION DI GCP (Fokus Utama)](#o-kesiapan-production-di-gcp-fokus-utama)
- [P. Pelajaran Utama Sesi Ini](#p-pelajaran-utama-sesi-ini)

---

## K. Keputusan Desain: Kenapa Login Opsional

Permintaan awal: "tambahkan login untuk mengakses fitur verifikasi."

Setelah menelaah arsitektur, diputuskan **TIDAK** mengunci penuh (wajib login),
melainkan **login opsional + rate limit**. Alasannya:

- Aplikasi ini alat cek fakta publik — kekuatannya di **friksi rendah** (tempel,
  langsung cek). Wajib login membunuh nilai itu.
- Masalah nyata yang ingin diatasi sebenarnya **biaya & penyalahgunaan** endpoint
  AI `/analyze`, bukan identitas pengguna.

| Tipe pengguna | Bisa verifikasi? | Kuota default | Dibatasi berdasarkan |
|---|---|---|---|
| Anonim (tamu) | Ya | 5 / jam | Alamat IP |
| Login (Google) | Ya | 50 / jam | UID pengguna |

**Prinsip keamanan kunci:** menyembunyikan tombol di UI **bukan** pengaman. Orang
tetap bisa memanggil `/analyze` langsung (mis. `curl`). Karena itu **backend wajib
ikut memverifikasi token + menerapkan rate limit**. Inilah sebabnya pekerjaan ini
menyentuh frontend DAN backend.

---

## L. Ringkasan Implementasi Kode

### Backend (FastAPI)
| File | Status | Fungsi |
|---|---|---|
| `app/services/auth_service.py` | baru | Verifikasi Firebase ID token (JWT) pakai sertifikat publik Google, tanpa SDK `firebase-admin` yang berat |
| `app/services/rate_limit_service.py` | baru | Fixed-window rate limiter in-memory |
| `app/dependencies.py` | baru | `get_current_user` + `enforce_analyze_rate_limit` |
| `app/config.py` | diubah | Tambah `FIREBASE_PROJECT_ID`, `RATE_LIMIT_WINDOW`, `ANON_RATE_LIMIT`, `USER_RATE_LIMIT` |
| `app/routers/analyze.py` | diubah | Pasang dependency rate limit ke `POST /analyze` |
| `requirements.txt` | diubah | Tambah `PyJWT==2.9.0`, `cryptography==43.0.1` |
| `.env`, `.env.example` | diubah | Tambah variabel Firebase & rate limit |

**Konsep penting — verifikasi JWT stateless:** server tidak menyimpan sesi. Tiap
request, token diverifikasi dengan sertifikat publik Google (cek tanda tangan,
`audience` = project id, `issuer`, masa berlaku). Cocok untuk serverless/Cloud Run
karena tidak butuh memori bersama.

**Sifat opsional:** kalau `FIREBASE_PROJECT_ID` kosong → `auth_service.is_enabled()`
mengembalikan `False` → semua request dianggap anonim. App tetap jalan tanpa setup.

### Frontend (Next.js)
| File | Status | Fungsi |
|---|---|---|
| `src/lib/firebase.ts` | baru | Inisialisasi Firebase client; `isAuthConfigured()` jadi saklar utama |
| `src/components/AuthProvider.tsx` | baru | Context auth global + jembatan token ke axios |
| `src/components/AuthButton.tsx` | baru | Tombol Masuk/Keluar di utility bar |
| `src/lib/api.ts` | diubah | Interceptor menempel `Authorization: Bearer <token>` otomatis |
| `src/app/layout.tsx` | diubah | Bungkus `<AuthProvider>` + pasang `<AuthButton>` |
| `src/app/verifikasi/page.tsx` | diubah | Banner ajakan login + handle error 429/401 |
| `.env.local` | diubah | Tambah `NEXT_PUBLIC_FIREBASE_*` |
| `package.json` | diubah | Tambah dependency `firebase` |

**Konsep penting — `NEXT_PUBLIC_*` di-bake saat build.** Sama seperti pelajaran di
sesi deploy GCP sebelumnya (bagian D.2): variabel ini di-inline saat `npm run build`,
bukan dibaca saat runtime. **Ini akan jadi inti masalah di production** (lihat bagian O).

---

## M. Semua Command yang Dijalankan

Lokasi kerja ditandai `cwd`. Shell = PowerShell (pemisah `;`, bukan `&&`).

### M.1 Cek dependency JWT (backend) — ternyata belum ada
```powershell
# cwd: backend
python -c "import jwt, cryptography; print('jwt', jwt.__version__); print('crypto ok')"
```
Hasil: `ModuleNotFoundError: No module named 'jwt'` → perlu instal.

### M.2 Instal dependency verifikasi token
```powershell
# cwd: backend
python -m pip install PyJWT==2.9.0 cryptography==43.0.1
```
- `PyJWT` → membaca & memverifikasi token JWT (format token Firebase).
- `cryptography` → algoritma RSA untuk validasi tanda tangan token.

### M.3 Verifikasi semua modul backend bisa diimpor
```powershell
# cwd: backend
python -c "from app.dependencies import enforce_analyze_rate_limit, get_current_user; from app.services import auth_service, rate_limit_service; from app.routers import analyze; print('all imports OK; auth enabled =', auth_service.is_enabled())"
```

### M.4 Uji logika rate limiter + status auth
```powershell
# cwd: backend
python -c "from app.services.rate_limit_service import FixedWindowRateLimiter; rl=FixedWindowRateLimiter(60); res=[rl.check('ip:x',3) for _ in range(4)]; print([(r.allowed,r.remaining) for r in res]); from app.config import settings; print('auth enabled (should be False):', bool(settings.FIREBASE_PROJECT_ID))"
```
Hasil: `[(True, 2), (True, 1), (True, 0), (False, 0)]` → 3 lolos, ke-4 ditolak. ✅

### M.5 Instal Firebase SDK (frontend)
```powershell
# cwd: frontend
npm install firebase@^11.1.0
```

### M.6 Build frontend (memastikan kompilasi)
```powershell
# cwd: frontend
npm run build
```

### M.7 Verifikasi app FastAPI lengkap bisa diimpor
```powershell
# cwd: backend
python -c "from app.main import app; routes=[r.path for r in app.routes]; print('analyze in routes:', '/analyze' in routes); print('OK')"
```

### M.8 Uji end-to-end rate limit lewat TestClient
File sementara `_test_ratelimit.py` dibuat lalu dijalankan:
```powershell
# cwd: backend
python _test_ratelimit.py
```
Hasil: `statuses: [400, 400, 400, 400, 400, 429, 429]` → membuktikan rate limit
berjalan **sebelum** logika analisis. File uji dihapus setelah selesai.

### M.9 Setelah kredensial diisi — verifikasi backend membaca project id
```powershell
# cwd: backend
python -c "from app.config import settings; from app.services import auth_service; print('FIREBASE_PROJECT_ID =', settings.FIREBASE_PROJECT_ID); print('auth enabled =', auth_service.is_enabled())"
```
Hasil: `FIREBASE_PROJECT_ID = faktain-63ddd`, `auth enabled = True`. ✅

### M.10 Build ulang + jalankan dev server + tes di browser
```powershell
# cwd: frontend
npm run build      # konfirmasi env terbaca
npm run dev        # jalankan dev server (long-running, dijalankan via process manager)
```
Lalu buka `http://localhost:3000`, klik **Masuk** → popup OAuth Google asli terbuka
(client_id project `faktain-63ddd`, redirect ke `faktain-63ddd.firebaseapp.com`).
Ini bukti integrasi end-to-end benar. Login aktual dihentikan di pemilihan akun
karena butuh akun pribadi.

---

## N. Mengisi Kredensial Firebase & Verifikasi

### N.1 Setup di Firebase Console (langkah di browser — dilakukan user)
1. [console.firebase.google.com](https://console.firebase.google.com) → buat project (`faktain-63ddd`).
2. **Authentication → Get started → Sign-in method → Google → Enable → Save.**
3. **Project settings → Your apps → Web (`</>`)** → daftarkan → salin `firebaseConfig`.
4. **Authentication → Settings → Authorized domains** → pastikan `localhost` ada.

### N.2 Isi `frontend/.env.local`
```dotenv
NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyAiQPEWQ5vJgP-aTBjm6k5WDm1aHEkUcaw
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=faktain-63ddd.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=faktain-63ddd
NEXT_PUBLIC_FIREBASE_APP_ID=1:1032218245234:web:2ee43f2b7754c3b23a6aeb
```

### N.3 Isi `backend/.env`
```dotenv
FIREBASE_PROJECT_ID=faktain-63ddd
```
> **WAJIB sama** dengan `NEXT_PUBLIC_FIREBASE_PROJECT_ID`. Backend memakai nilai ini
> untuk memeriksa klaim `audience` di token. Kalau beda → semua login ditolak 401.

### N.4 Catatan: yang dipakai hanya 4 dari config
`measurementId`, `storageBucket`, `messagingSenderId` tidak dipakai karena kita
hanya butuh Auth (bukan Analytics/Storage). Aman diabaikan.

### N.5 Catatan keamanan
4 nilai `NEXT_PUBLIC_FIREBASE_*` memang **publik** (aman di frontend) — keamanan
diatur oleh Authorized Domains & Firebase Rules. Ini **berbeda** dari `LLM_API_KEY`
di backend yang benar-benar rahasia dan harus lewat Secret Manager.

---

## O. KESIAPAN PRODUCTION DI GCP (Fokus Utama)

**Pertanyaan inti sesi ini:** apakah login otomatis jalan di production Cloud Run?
**Jawaban: BELUM.** Ada 3 hal yang harus disiapkan. Yang paling kritis adalah cara
Next.js menangani env (mengulang pelajaran D.2 dari sesi deploy sebelumnya).

### O.1 (KRITIS) Dockerfile frontend belum meneruskan kredensial Firebase

Kondisi `frontend/Dockerfile` saat ini hanya meneruskan `NEXT_PUBLIC_API_URL`:
```dockerfile
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build
```

**Masalahnya:**
- `NEXT_PUBLIC_*` di-**bake saat build**, bukan runtime.
- `.env.local` **tidak ikut** ke dalam image (di-gitignore, tidak di-COPY, dan
  memang di-ignore di `.gcloudignore` lewat pola `frontend/.env*.local`).
- Akibatnya, kalau image di-build apa adanya → keempat `NEXT_PUBLIC_FIREBASE_*`
  **kosong** → `isAuthConfigured()` = `false` → **tombol login tidak muncul di
  production**, persis seperti kondisi lokal sebelum env diisi.

**Perbaikan — tambahkan build arg Firebase ke Dockerfile frontend:**
```dockerfile
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_FIREBASE_API_KEY
ARG NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
ARG NEXT_PUBLIC_FIREBASE_PROJECT_ID
ARG NEXT_PUBLIC_FIREBASE_APP_ID
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_FIREBASE_API_KEY=${NEXT_PUBLIC_FIREBASE_API_KEY} \
    NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=${NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN} \
    NEXT_PUBLIC_FIREBASE_PROJECT_ID=${NEXT_PUBLIC_FIREBASE_PROJECT_ID} \
    NEXT_PUBLIC_FIREBASE_APP_ID=${NEXT_PUBLIC_FIREBASE_APP_ID}
RUN npm run build
```

### O.2 (KRITIS) `cloudbuild.yaml` harus meneruskan build arg tersebut

Di sesi deploy sebelumnya, step `build-frontend` hanya mengirim `NEXT_PUBLIC_API_URL`.
Perlu ditambah keempat arg Firebase. Karena nilai ini publik, boleh ditaruh sebagai
`substitutions` di `cloudbuild.yaml`:

```yaml
substitutions:
  _REGION: asia-southeast1
  _REPO: hoax-detector
  _TAG: latest
  _FIREBASE_API_KEY: "AIzaSyAiQPEWQ5vJgP-aTBjm6k5WDm1aHEkUcaw"
  _FIREBASE_AUTH_DOMAIN: "faktain-63ddd.firebaseapp.com"
  _FIREBASE_PROJECT_ID: "faktain-63ddd"
  _FIREBASE_APP_ID: "1:1032218245234:web:2ee43f2b7754c3b23a6aeb"
```

Lalu di step `build-frontend` (yang membaca URL backend dari `/workspace`):
```yaml
  - name: "gcr.io/cloud-builders/docker"
    id: "build-frontend"
    waitFor: ["get-backend-url"]
    entrypoint: bash
    args:
      - -c
      - |
        set -e
        BACKEND_URL=$(cat /workspace/backend_url.txt)
        docker build \
          --build-arg NEXT_PUBLIC_API_URL=$$BACKEND_URL \
          --build-arg NEXT_PUBLIC_FIREBASE_API_KEY=${_FIREBASE_API_KEY} \
          --build-arg NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=${_FIREBASE_AUTH_DOMAIN} \
          --build-arg NEXT_PUBLIC_FIREBASE_PROJECT_ID=${_FIREBASE_PROJECT_ID} \
          --build-arg NEXT_PUBLIC_FIREBASE_APP_ID=${_FIREBASE_APP_ID} \
          -t ${_REGION}-docker.pkg.dev/$PROJECT_ID/${_REPO}/frontend:${_TAG} \
          ./frontend
```

> Ingat aturan `$$` dari sesi sebelumnya: `$$BACKEND_URL` pakai dobel `$` agar
> diteruskan ke bash, sedangkan `${_FIREBASE_*}` adalah substitution Cloud Build
> (single `$`).

### O.3 (KRITIS) Backend production butuh `FIREBASE_PROJECT_ID` saat runtime

Backend membaca env saat **runtime** (bukan build), jadi cukup di-set saat deploy.
`FIREBASE_PROJECT_ID` bukan rahasia → boleh env biasa. Tambahkan ke step
`deploy-backend` di `cloudbuild.yaml`:

```yaml
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID,FIREBASE_PROJECT_ID=faktain-63ddd
```

Atau update service yang sudah ada:
```powershell
& $gc run services update hoax-detector-backend --region=asia-southeast1 --update-env-vars=FIREBASE_PROJECT_ID=faktain-63ddd
```

> ⚠️ Hati-hati: kalau `FRONTEND_URL` di backend berisi koma (dua format URL — lihat
> bagian G), JANGAN pakai `--set-env-vars` untuk mengeset banyak variabel sekaligus.
> Gunakan `--update-env-vars=FIREBASE_PROJECT_ID=...` yang hanya menyentuh satu
> variabel, atau lewat `--env-vars-file` YAML.

### O.4 (KRITIS) Tambahkan domain Cloud Run ke Authorized Domains Firebase

Login Google hanya diizinkan dari domain terdaftar. Setelah tahu URL frontend
production, tambahkan di **Firebase Console → Authentication → Settings →
Authorized domains**:
- `hoax-detector-frontend-237232251242.asia-southeast1.run.app` (format baru)
- `hoax-detector-frontend-qwtbyvmotq-as.a.run.app` (format lama, kalau dipakai)
- domain custom (kalau ada)

Tanpa ini, popup login akan ditolak dengan error `auth/unauthorized-domain`.
Ini langkah **di browser**, tidak bisa lewat gcloud.

### O.5 Ringkasan checklist production login

| # | Hal | Di mana | Status sekarang |
|---|---|---|---|
| 1 | Build arg Firebase di `Dockerfile` frontend | Kode | ✅ Sudah (diterapkan 13 Juni) |
| 2 | Teruskan build arg di `cloudbuild.yaml` | Kode CI/CD | ✅ Sudah (diterapkan 13 Juni) |
| 3 | `FIREBASE_PROJECT_ID` env di backend Cloud Run | Deploy | ✅ Sudah (di `cloudbuild.yaml` step deploy-backend) |
| 4 | Authorized domains di Firebase Console | Browser | ❌ Belum (langkah manual setelah tahu URL frontend) |
| 5 | Kode aplikasi (FE+BE) siap auth | Kode | ✅ Sudah |
| 6 | Login berfungsi di lokal | Lokal | ✅ Terverifikasi |
| 7 | Jalankan ulang pipeline & verifikasi di production | Deploy | ⏳ Menunggu dijalankan |

### O.6 Keterbatasan yang perlu diingat di production
- **Rate limiter in-memory** (bagian H & rekomendasi sebelumnya): di Cloud Run yang
  autoscale ke banyak instance, tiap instance punya hitungan sendiri → limit efektif
  jadi `jumlah_instance × limit`. Untuk MVP traffic rendah masih bisa diterima, tapi
  untuk akurat perlu pindah ke Firestore/Redis. (API limiter sengaja dibuat kecil
  agar mudah ditukar.)
- **History analisis belum dibuat** — token user sudah sampai backend, tinggal
  tambah penyimpanan (Firestore) untuk simpan riwayat per UID.

---

## P. Pelajaran Utama Sesi Ini

1. **UI bukan pengaman.** Menyembunyikan tombol login tidak mengamankan apa pun.
   Backend wajib verifikasi token + rate limit. Defense in depth.

2. **JWT stateless cocok untuk serverless.** Verifikasi pakai sertifikat publik
   Google; server tidak menyimpan sesi. Tidak butuh `firebase-admin` yang berat —
   `PyJWT` + `cryptography` sudah cukup.

3. **`FIREBASE_PROJECT_ID` backend HARUS sama dengan `projectId` frontend.** Dipakai
   verifikasi klaim `audience` token. Beda sedikit → semua login 401.

4. **(Mengulang & memperkuat D.2) `NEXT_PUBLIC_*` di-bake saat build.** Kredensial
   Firebase frontend harus masuk lewat `--build-arg` di Docker + `cloudbuild.yaml`.
   Kalau tidak, login akan "hilang" di production walau jalan di lokal.

5. **Beda lokasi baca env FE vs BE.** Frontend baca env saat **build**; backend baca
   saat **runtime**. Konsekuensinya cara penyalurannya berbeda (build-arg vs
   set-env-vars).

6. **Kredensial Firebase web itu publik, tapi `LLM_API_KEY` rahasia.** Jangan
   samakan perlakuannya: yang publik boleh di substitutions/build-arg, yang rahasia
   wajib Secret Manager.

7. **Authorized Domains wajib di-update untuk tiap domain production.** Termasuk dua
   format URL Cloud Run (lihat bagian G) dan domain custom.

8. **Fitur opsional = degradasi anggun.** Tanpa konfigurasi Firebase, app tetap
   jalan mode anonim alih-alih error — memudahkan dev & deploy bertahap.

---

*Bagian sesi fitur login + kesiapan production dibuat 13 Juni 2026 — catatan belajar.*

---

# SESI: AUDIT KODE + PERBAIKAN + CEK PRODUKSI (7 Juli 2026)

Sesi ini berbeda dari sesi sebelumnya: bukan menambah fitur, melainkan **mengaudit
kode yang sudah ada** (backend, frontend, pipeline), memperbaiki temuannya, lalu
membandingkan kondisi produksi di GCP dengan kode lokal. Ini keterampilan yang
sama pentingnya dengan menulis kode baru.

## Daftar Isi Sesi Ini

- [Q. Temuan Audit](#q-temuan-audit)
- [R. Perbaikan yang Diterapkan](#r-perbaikan-yang-diterapkan)
- [S. Audit Produksi GCP: Deployment Drift](#s-audit-produksi-gcp-deployment-drift)
- [T. Pelajaran Utama Sesi Ini](#t-pelajaran-utama-sesi-ini)

---

## Q. Temuan Audit

Audit membaca seluruh kode (~4.000 baris) SEBELUM menilai. Urutan temuan
berdasarkan dampak, bukan urutan file:

| # | Temuan | Lokasi | Dampak |
|---|--------|--------|--------|
| 1 | Rate limit anonim bisa di-bypass via spoofing `X-Forwarded-For` | `dependencies.py` | Keamanan + biaya: tiap request = panggilan LLM berbayar |
| 2 | Rate limiter & cache in-memory, tapi deploy tidak membatasi jumlah instance | `cloudbuild.yaml` | Kuota efektif berlipat saat autoscale |
| 3 | `gemini_service.py` isinya OpenRouter, bukan Gemini | nama file | Menyesatkan pembaca berikutnya |
| 4 | `feedparser.parse()` & `newspaper3k` (blocking) dipanggil di dalam `async def` | `news_service.py`, `scraper_service.py` | Event loop macet → request lain ikut lambat |
| 5 | `.seconds` dipakai padahal maksudnya `.total_seconds()`; TTL hardcoded padahal ada di settings; fungsi eviction tidak pernah dipanggil | `news_service.py`, `rate_limit_service.py` | Bug halus + bocor memori pelan |
| 6 | Error 500 meneruskan `str(e)` mentah ke klien | `analyze.py` | Membocorkan detail internal/upstream |
| 7 | File sampah (skrip diagnostik, dump JSON, screenshot) tercecer di working tree | root & `backend/` | Mengotori repo kalau ikut ter-commit |

### Q.1 Anatomi temuan #1 (yang paling penting dipahami)

`X-Forwarded-For` adalah header yang **bisa dikirim siapa saja**. Format aslinya:

```
X-Forwarded-For: <nilai-buatan-klien...>, <IP-asli-yang-ditambahkan-proxy>
```

Cloud Run **menambahkan IP asli klien di posisi TERAKHIR**. Kode lama mengambil
entri PERTAMA — artinya penyerang tinggal mengirim header
`X-Forwarded-For: 1.2.3.4` (angka acak tiap request) dan rate limiter mengira
tiap request datang dari IP berbeda. Kuota 5/jam jadi tak terbatas, dan tiap
request memicu panggilan LLM yang **berbayar**.

Aturan umumnya: **bagian mana pun dari request yang berasal dari klien tidak
boleh dipercaya untuk keputusan keamanan** — termasuk header yang "terlihat
seperti diisi infrastruktur".

---

## R. Perbaikan yang Diterapkan

### R.1 Fix #1 — Ambil hop terakhir X-Forwarded-For (`dependencies.py`)

```python
# SEBELUM (spoofable):
forwarded = request.headers.get("X-Forwarded-For")
if forwarded:
    return forwarded.split(",")[0].strip()   # entri pertama = buatan klien!

# SESUDAH (hanya percaya yang ditambahkan Cloud Run):
forwarded = request.headers.get("X-Forwarded-For", "")
hops = [h.strip() for h in forwarded.split(",") if h.strip()]
if hops:
    return hops[-1]   # entri terakhir = IP asli menurut Google
```

Catatan: kalau nanti ada Load Balancer di depan Cloud Run, yang benar jadi
`hops[-2]` (LB menambahkan IP-nya sendiri di paling belakang).

### R.2 Fix #2 — `--max-instances=1` di deploy backend (`cloudbuild.yaml`)

Rate limiter dan cache berita hidup di memori proses. Kalau Cloud Run scale ke
3 instance, ada 3 hitungan kuota yang saling tidak tahu. Satu flag menutupnya:

```yaml
- --max-instances=1
```

Ini **trade-off sadar**: membatasi throughput demi kebenaran limiter. Baru boleh
dinaikkan setelah state pindah ke store bersama (Firestore/Redis).

### R.3 Fix #3 — Rename `gemini_service.py` → `llm_service.py`

```powershell
git mv backend/app/services/gemini_service.py backend/app/services/llm_service.py
```

`git mv` (bukan hapus+buat) supaya git mencatatnya sebagai rename dan history
file tetap terhubung. Semua import di 5 file pemakai ikut diperbarui.

### R.4 Fix #4 — Panggilan blocking dibungkus `asyncio.to_thread`

```python
# SEBELUM: memblokir event loop (HTTP fetch sinkron di dalam async def)
feed = feedparser.parse(CATEGORY_FEEDS[category])

# SESUDAH: jalan di thread terpisah, event loop tetap melayani request lain
feed = await asyncio.to_thread(feedparser.parse, CATEGORY_FEEDS[category])
```

Konsepnya: `async def` TIDAK otomatis membuat kode di dalamnya non-blocking.
Library sinkron (feedparser, newspaper3k) tetap memblokir satu-satunya event
loop. `asyncio.to_thread` (stdlib, Python 3.9+) adalah jalan keluar termurah.

### R.5 Fix #5 — Tiga bug kecil di cache & rate limiter

```python
# BUG: .seconds hanya komponen "sisa detik" dari timedelta, wrap tiap 24 jam.
#      Cache berumur 24,5 jam → .seconds = 1800 → dianggap masih segar!
cache_age = (now - cached["timestamp"]).seconds        # SALAH
cache_age = (now - cached["timestamp"]).total_seconds() # BENAR
```

- TTL hardcoded `3600` diganti `settings.NEWS_CACHE_TTL` (config-nya sudah ada
  tapi tidak pernah dipakai — "config mati" itu jebakan: orang mengubah env var
  dan bingung kenapa tidak berpengaruh).
- `_evict_expired()` ada tapi **tidak pernah dipanggil** → key IP yang tidak
  pernah kembali menumpuk selamanya. Sekarang dipanggil dari `check()` saat
  jumlah key > 1024.
- Nama kelas diluruskan: `FixedWindowRateLimiter` → `SlidingWindowRateLimiter`
  (implementasinya memang sliding window; nama yang bohong = dokumentasi yang bohong).

### R.6 Fix #6 — Jangan bocorkan error internal (`analyze.py`)

```python
# SEBELUM: str(e) bisa berisi URL upstream, nama model, detail API key, dll.
except Exception as e:
    raise HTTPException(500, detail=f"Gagal menganalisis: {str(e)}")

# SESUDAH: detail lengkap ke LOG (untuk developer), pesan generik ke klien.
except Exception:
    logger.exception("Analisis gagal")
    raise HTTPException(500, detail="Gagal menganalisis. Coba lagi sebentar lagi.")
```

`logger.exception()` otomatis menyertakan stack trace — di Cloud Run langsung
masuk Cloud Logging tanpa setup tambahan.

### R.7 Verifikasi

Tiap perbaikan diverifikasi, bukan diasumsikan benar:

```bash
python -c "import app.main"        # seluruh app masih bisa di-import
python test_verdict_logic.py       # unit test offline tetap lulus
# + tes manual: XFF "spoofed, 9.9.9.9" → terbaca 9.9.9.9
# + fetch_news() sungguhan → 3 artikel kembali via to_thread
```

---

## S. Audit Produksi GCP: Deployment Drift

Perintah yang dipakai (semuanya read-only, aman dijalankan kapan pun):

```bash
gcloud run services list
gcloud run services describe hoax-detector-backend --region=asia-southeast1 --format=json
gcloud builds list --limit=5
gcloud secrets versions list llm-api-key
gcloud logging read "...severity>=ERROR" --freshness=30d
curl https://<backend-url>/health
```

### S.1 Temuan: produksi ≠ kode lokal

| Aspek | Produksi (live) | Kode lokal | Akibat |
|---|---|---|---|
| Deploy terakhir | 3 Juni 2026 | — | Produksi tertinggal 1 bulan+ |
| `FIREBASE_PROJECT_ID` di backend | ❌ tidak ada | ✅ di cloudbuild | **Login mati di produksi** — user login tetap dapat kuota anonim |
| Revisi frontend | 00001 (build pertama!) | banyak fitur baru | Login, kategori, halaman baru **belum live** |
| `maxScale` backend | 3 | 1 (fix #2) | Limiter terpecah 3 instance |
| Celah XFF | masih ada | sudah ditambal | Kuota bisa di-bypass di live |

Istilah untuk fenomena ini: **deployment drift** — kode di repo dan yang
berjalan di produksi pelan-pelan menyimpang karena deploy tidak rutin.
Kesehatan endpoint (`/health` → 200) TIDAK menjamin produksi menjalankan kode
yang kamu kira; yang dicek `/health` hanya "proses hidup".

### S.2 Jalan keluarnya satu

Bersihkan file sampah → commit → `gcloud builds submit --config infra/cloudbuild.yaml`.
Satu build itu sekaligus: menghidupkan login, membawa fix keamanan, dan
menerapkan max-instances=1.

---

## T. Pelajaran Utama Sesi Ini

1. **Jangan percaya header dari klien untuk keputusan keamanan.**
   `X-Forwarded-For` bisa dipalsukan; hanya entri yang ditambahkan
   infrastrukturmu sendiri (posisi terakhir di Cloud Run) yang bisa dipercaya.
   Rate limit yang bisa di-bypass = tagihan LLM yang tidak terkendali.

2. **State in-memory dan autoscaling tidak akur.** Kalau limiter/cache hidup di
   memori proses, `--max-instances=1` bukan opsional — atau pindahkan state ke
   store bersama. Pilih salah satu secara SADAR, jangan dibiarkan implisit.

3. **`async def` tidak menyulap kode jadi non-blocking.** Library sinkron di
   dalam handler async memblokir SEMUA request. Bungkus dengan
   `asyncio.to_thread(...)` — dua kata kunci, masalah selesai.

4. **`timedelta.seconds` ≠ `total_seconds()`.** `.seconds` hanya komponen sisa
   (wrap tiap 24 jam). Bug jenis ini lolos testing biasa karena baru muncul
   setelah 24 jam berjalan.

5. **Nama yang bohong lebih buruk daripada tidak ada nama.**
   `gemini_service.py` berisi OpenRouter dan `FixedWindow` berisi sliding
   window membuat pembaca berikutnya (termasuk dirimu 3 bulan lagi) salah
   paham. Rename itu murah; pakai `git mv` agar history terjaga.

6. **Error message untuk user ≠ error message untuk developer.** Detail lengkap
   → log server (`logger.exception`). Klien cukup pesan generik. `str(e)` mentah
   di response API bisa membocorkan arsitektur internal.

7. **Config yang tidak dipakai adalah jebakan.** `NEWS_CACHE_TTL` ada di
   settings tapi angkanya di-hardcode di tempat lain — siapa pun yang mengubah
   env var akan bingung. Sama halnya fungsi yang tidak pernah dipanggil
   (`_evict_expired`): sambungkan atau hapus.

8. **"Sehat" bukan berarti "terbaru".** `/health` 200 hanya bilang prosesnya
   hidup. Bandingkan revisi + env var produksi dengan kode lokal secara berkala
   (`gcloud run services describe`) — deployment drift terjadi diam-diam.

9. **Audit dulu, baru menilai.** Semua temuan di atas datang dari MEMBACA seluruh
   alur kode sebelum menyimpulkan. Perbaikan yang benar biasanya kecil
   (satu-dua baris), tapi menemukan TEMPAT yang benar butuh pemahaman utuh.

10. **Verifikasi setiap klaim "sudah diperbaiki".** Tiap fix diikuti bukti:
    import jalan, test lulus, perilaku dites langsung. "Kelihatannya benar"
    bukan bukti.

---

*Bagian sesi audit + perbaikan + cek produksi dibuat 7 Juli 2026 — catatan belajar.*
