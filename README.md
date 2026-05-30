# 🛡️ Anti-Hoax — Pendeteksi Hoaks Berbasis AI

Aplikasi web yang membantu pengguna Indonesia memverifikasi kredibilitas berita secara real-time menggunakan Gemini AI dengan Google Search Grounding.

## Tech Stack

- **Frontend:** Next.js 14 + TypeScript + Tailwind CSS
- **Backend:** FastAPI + Python 3.11
- **AI:** Gemini 2.0 Flash + Google Search Grounding
- **Infra:** Google Cloud Platform (Cloud Run, Firestore, Artifact Registry)

## Fitur

- ✅ Analisis teks berita atau URL artikel
- ✅ Skor kepercayaan 0-100 dengan badge verdict
- ✅ Identifikasi indikator hoaks
- ✅ Verifikasi klaim dengan sumber terpercaya
- ✅ News feed berita Indonesia terkini
- ✅ Desain bergaya koran cetak klasik

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
cp .env.example .env
# Edit .env dan masukkan GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Buka http://localhost:3000 di browser.

## API Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| POST | `/analyze` | Analisis teks/URL berita |
| GET | `/news` | Ambil news feed Indonesia |
| GET | `/news/{id}/analyze` | Analisis artikel dari news feed |
| GET | `/docs` | Swagger UI dokumentasi API |

## Environment Variables

### Backend (.env)
- `GEMINI_API_KEY` — API key dari Google AI Studio
- `GCP_PROJECT_ID` — ID project GCP
- `FRONTEND_URL` — URL frontend untuk CORS

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL` — URL backend API

## Deploy ke GCP

Lihat `infra/cloudbuild.yaml` untuk CI/CD pipeline otomatis.

## Lisensi

MIT
