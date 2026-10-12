# FAKTANYA

**Terlihat asli. Apa faktanya?**

Aplikasi verifikasi informasi berbahasa Indonesia untuk IBM SkillsBuild Hackathon.
Periksa teks, URL artikel, atau screenshot dengan caption opsional, lalu tinjau
klaim dan kutipan dari sumber pendukung maupun pembantah.

## Fitur

- **Cek Berita:** verifikasi klaim dari teks atau URL artikel.
- **Verifikasi Timpa Teks:** baca teks pada screenshot dan periksa klaim serta
  konteks gambarnya. Buka `/verifikasi?mode=timpa-teks` untuk langsung mengunggah gambar.
- **Berita terbaru:** feed Google News per kategori dan ringkasan isi artikel.
- **Login Google opsional:** Firebase Authentication dengan kuota analisis tamu/login.

Hasil menyertakan alasan, tautan sumber, kutipan, dan keterbatasan pemeriksaan.
Verdict klaim: `SUPPORTED`, `CONTRADICTED`, `MISLEADING`, `PARTIALLY_SUPPORTED`,
atau `INSUFFICIENT_EVIDENCE`. Verdict konteks gambar: `VERIFIED_CONTEXT`,
`MISLEADING_CONTEXT`, atau `INSUFFICIENT_EVIDENCE`.

Aplikasi tidak membuktikan suatu gambar telah diedit dan tidak melakukan deteksi
forensik/deepfake. Klaim yang salah tidak otomatis membuktikan timpa teks.

## Arsitektur

```text
Next.js -> FastAPI -> Langflow -> 9Router (model teks/vision)
                       |
                       +-> callback FastAPI -> DuckDuckGo -> artikel sumber
                       |
                       +-> FastAPI memvalidasi schema, ID sumber, dan kutipan
```

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS 4.
- Backend: FastAPI, Python 3.11+; pengujian lokal menggunakan Python 3.12.
- Orkestrasi AI: Langflow 1.12.1 dengan tiga flow untuk teks, gambar, dan ringkasan.
- Model: provider OpenAI Compatible 9Router; ID model mengikuti katalog instance.
- Pencarian sumber: DuckDuckGo HTML, tanpa API key pencarian.
- Autentikasi: Firebase, opsional.

## Struktur proyek

```text
backend/       API, validasi, pencarian bukti, dan tes Python
frontend/      Antarmuka Next.js dan tes browser
langflow/      Komponen workflow dan ekspor tiga flow
flow.json      Ekspor flow verifikasi teks
infra/         Template deployment Cloud Build
docs/         Panduan Langflow, demo, login, dan catatan validasi
```

## Menjalankan lokal

Prasyarat: Python 3.12, Node.js 20.9+, npm, instance 9Router, dan Langflow 1.12.1.
Langflow dijalankan terpisah dari backend; dependency backend tidak memasangnya.

### 1. Siapkan backend

Dari root repository, menggunakan PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

Di Linux/macOS, buat virtual environment dengan `python3 -m venv .venv`,
lalu gunakan `.venv/bin/python` sebagai pengganti `.venv\Scripts\python.exe`.

### 2. Konfigurasikan 9Router dan Langflow

Impor `langflow/text-verification.json`, `langflow/image-verification.json`, dan
`langflow/news-summary.json` ke Langflow. Konfigurasikan provider, model teks/vision,
Backend URL untuk callback, serta Service Key sesuai [panduan Langflow](docs/LANGFLOW.md).
Ekspor tidak menyertakan kredensial; setiap instance perlu dikonfigurasi sendiri.

Isi `backend/.env` dari template. Nilai yang perlu disesuaikan:

| Variabel | Isi |
| --- | --- |
| `LLM_BASE_URL` | URL 9Router yang dapat diakses backend, termasuk `/v1` |
| `LLM_API_KEY` | Key instance 9Router |
| `LLM_MODEL` | ID model teks dari katalog instance |
| `LLM_VISION_MODEL` | ID model yang telah dikonfirmasi mendukung gambar |
| `LANGFLOW_URL` | URL instance Langflow yang dapat diakses backend |
| `LANGFLOW_API_KEY` | Key instance Langflow |
| `LANGFLOW_SERVICE_KEY` | Secret callback yang sama dengan Service Key komponen Langflow |
| `LANGFLOW_TEXT_FLOW_ID` | ID flow verifikasi teks |
| `LANGFLOW_IMAGE_FLOW_ID` | ID flow verifikasi gambar |
| `LANGFLOW_SUMMARY_FLOW_ID` | ID flow ringkasan |
| `FRONTEND_URL` | Origin frontend untuk CORS; lokal `http://localhost:3000` |

Pertahankan `ORCHESTRATION_BACKEND=langflow`, `LLM_WEB_MODE=external`, dan
`SEARCH_PROVIDER=duckduckgo`. Jika DNS lokal memblokir DuckDuckGo, opsi
`SEARCH_DNS_OVER_HTTPS=true` tersedia khusus untuk hostname pencarian.
Langflow tidak otomatis membaca `.env` backend.

Backend memeriksa katalog model dan konfigurasi saat startup. Jika metadata
katalog tidak menyatakan dukungan gambar, isi `LLM_VISION_MODELS` hanya setelah
mengonfirmasi dukungan vision dari upstream. Model text-only tetap ditolak.

### 3. Jalankan backend dan frontend

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Di terminal lain:

```powershell
cd frontend
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
# Sesuaikan NEXT_PUBLIC_API_URL; konfigurasi Firebase opsional.
npm run dev
```

Buka frontend di `http://localhost:3000`, API docs di `http://localhost:8000/docs`.
Cek provider melalui `http://localhost:8000/health/llm`. Pemeriksaan katalog bukan
jaminan chat/OCR berhasil; uji teks dan gambar setelah konfigurasi.

Untuk login Google, lihat [panduan Firebase](docs/PANDUAN-FITUR-LOGIN.md).
Tanpa konfigurasi Firebase, aplikasi tetap berjalan dalam mode tamu.

## API

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| POST | `/analyze` | Verifikasi teks, URL, atau gambar dengan caption opsional |
| GET | `/news?category=teknologi&limit=20` | Feed Google News |
| GET | `/news/categories` | Daftar kategori |
| GET | `/news/{id}/summarize` | Ringkasan artikel asli |
| GET | `/health` | Liveness backend |
| GET | `/health/llm` | Katalog/model provider; HTTP 503 saat gagal |

Contoh body teks:

```json
{"text": "Indonesia merdeka pada 17 Agustus 1945"}
```

Untuk URL gunakan `{"url":"https://contoh.com/artikel"}`. Untuk gambar gunakan
`{"image_data_url":"data:image/png;base64,...","text":"Caption opsional"}`.
Respons analisis memakai `schema_version: "2.0"`, `claims`, dan evidence per klaim.

## Pengujian

Dari root repository:

```powershell
.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend -q
cd frontend
npm run lint
npm run typecheck
npm run test:e2e -- --workers=1
npm run build
```

Playwright memakai Chrome terpasang pada Windows. Di Linux, jalankan
`npx playwright install chromium` terlebih dahulu. Tes UI menggunakan API mock;
tes live hanya berjalan jika `FAKTAIN_LIVE_SMOKE=1` dan layanan sudah dikonfigurasi.
Contoh integrasi dan hasil pengujian sebelumnya tersedia di
[panduan Langflow](docs/LANGFLOW.md) dan [catatan validasi MVP](docs/MVP_VALIDATION.md).
Hasil tersebut tidak membuktikan akurasi faktual untuk semua input.

## Deployment

Dockerfile frontend/backend tersedia. Langflow dan 9Router harus berjalan dan
bisa dijangkau backend; callback Langflow juga harus bisa menjangkau backend.
Keduanya bisa berada di server yang sama atau layanan terpisah.

- Gunakan URL layanan/network container yang sesuai; `localhost` dalam container
  menunjuk container itu sendiri.
- `NEXT_PUBLIC_*` frontend ditetapkan saat build. URL API harus dapat diakses browser.
- Sesuaikan CORS, HTTPS, autentikasi, dan kuota sebelum membuka akses publik.
- Jalankan backend dengan satu worker: session callback, rate limiter, dan cache
  masih disimpan dalam memori proses. Multiworker tanpa affinity tidak didukung.
- `infra/cloudbuild.yaml` adalah template lama yang perlu dilengkapi konfigurasi
  Langflow, URL/model 9Router, dan secret sebelum digunakan untuk revisi ini.
  Substitusi Firebase sengaja kosong; isi melalui konfigurasi deployment Anda.

Panduan ini tidak menyatakan aplikasi sudah dideploy.

## Keamanan dan batasan

- Jangan commit `.env`, API key, private key, atau service-account JSON.
  Gunakan template `.env.example`; variabel `NEXT_PUBLIC_*` terlihat oleh browser.
- `.gitignore` mengecualikan konfigurasi editor/agent, catatan koneksi server lokal,
  dependency, cache, hasil build, dan hasil tes. File lokal tetap ada di komputer.
- Gambar JPEG/PNG/WebP maksimal 5 MiB dan 16 megapiksel; diperkecil hingga
  1600 piksel per sisi dan metadata dilepas. OCR teks kecil dapat gagal.
- URL artikel harus publik; redirect/DNS dan ukuran unduhan divalidasi.
  Sumber paywall atau yang memerlukan JavaScript dapat tidak terbaca.
- Batas analisis: maksimal 3 klaim, 5 pengambilan artikel evidence, 2 gambar kandidat,
  2 putaran pencarian, 8 panggilan model, dan deadline default 100 detik.
- Kuota default: tamu 5 analisis per IP dan login 50 per UID setiap jam.
- DuckDuckGo dapat membatasi akses atau memberikan CAPTCHA. Kegagalan pencarian
  dan kekurangan bukti ditampilkan sebagai keterbatasan, bukan tebakan verdict.
- Teks/gambar dikirim ke penyedia AI. Atur privasi runtime Langflow mengikuti
  [panduan privasi](docs/LANGFLOW.md); ekspor flow saja tidak menjamin privasi runtime.
- Kutipan tervalidasi dan kesamaan visual tidak menjamin sumber benar.
  Tinjau artikel asli sebelum membagikan kesimpulan.

## Dokumentasi

- [Setup, arsitektur, dan privasi Langflow](docs/LANGFLOW.md)
- [Skenario demo](docs/LANGFLOW_DEMOS.md)
- [Komponen dan ekspor flow](langflow/README.md)
- [Validasi dan batas MVP](docs/MVP_VALIDATION.md)
- [Login Google/Firebase](docs/PANDUAN-FITUR-LOGIN.md)
