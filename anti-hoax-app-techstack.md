# 🛡️ Aplikasi AI Pendeteksi Hoaks — Dokumen Tech Stack & Rencana Pengembangan

> **Versi:** 1.0  
> **Stack:** Next.js · FastAPI · Gemini API · Google Cloud Platform  
> **Target:** Web App Pendeteksi Hoaks untuk Pengguna Indonesia

---

## Daftar Isi

1. [Gambaran Umum](#1-gambaran-umum)
2. [Arsitektur Sistem](#2-arsitektur-sistem)
3. [Tech Stack Lengkap](#3-tech-stack-lengkap)
4. [Struktur Folder Project](#4-struktur-folder-project)
5. [AI & Gemini API](#5-ai--gemini-api)
6. [Infrastruktur GCP](#6-infrastruktur-gcp)
7. [CI/CD Pipeline](#7-cicd-pipeline)
8. [Fitur Aplikasi](#8-fitur-aplikasi)
9. [Rencana Pengembangan](#9-rencana-pengembangan)
10. [Estimasi Biaya GCP](#10-estimasi-biaya-gcp)

---

## 1. Gambaran Umum

Aplikasi web berbasis AI yang membantu pengguna Indonesia memverifikasi kredibilitas berita secara real-time. Pengguna dapat memasukkan teks berita atau URL, lalu sistem akan menganalisis konten menggunakan Gemini API dengan Google Search Grounding untuk memberikan verdict berbasis bukti dari internet.

### Kemampuan Utama

| Fitur | Deskripsi |
|---|---|
| Analisis teks/URL | Input berita dalam bentuk teks mentah atau URL artikel |
| Verifikasi real-time | Gemini search Google secara native sebelum memberikan verdict |
| Skor kredibilitas | Nilai 0–100 berdasarkan analisis pola dan verifikasi fakta |
| Badge verdict | `KREDIBEL` / `PERLU DICEK` / `KEMUNGKINAN HOAKS` |
| News feed | Berita terkini dari Indonesia dengan ringkasan AI |
| History analisis | Riwayat pengecekan tersimpan di Firestore |

---

## 2. Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────┐
│                    USER (Browser)                           │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloud Run — Next.js Frontend                   │
│         (SSR + Static + API Routes)                        │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloud Run — FastAPI Backend                    │
│    /analyze  |  /news  |  /news/{id}/analyze               │
└──────┬─────────────────┬──────────────────────┬────────────┘
       │                 │                      │
       ▼                 ▼                      ▼
┌────────────┐  ┌─────────────────┐  ┌──────────────────────┐
│ Gemini API │  │  Google News    │  │      Firestore       │
│ (AI Studio)│  │  RSS Feed       │  │  (History & Cache)   │
│ + Search   │  │  hl=id&gl=ID    │  │                      │
│ Grounding  │  └─────────────────┘  └──────────────────────┘
└────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│              Google Search (via Grounding)                  │
│     Kompas · Tempo · BBC Indonesia · Turnbackhoax          │
└─────────────────────────────────────────────────────────────┘
```

### Alur Analisis Berita

```
Input User (teks / URL)
        │
        ▼
[Jika URL] newspaper3k scrape konten artikel
        │
        ▼
FastAPI kirim ke Gemini 2.0 Flash
        │
        ├── Gemini aktifkan Google Search Grounding
        │         │
        │         ▼
        │   Search sumber terpercaya Indonesia
        │   (Kompas, Tempo, Cekfakta, Turnbackhoax)
        │
        ▼
Gemini analisis + sintesis hasil search
        │
        ▼
Output JSON terstruktur:
  - confidence_score (0–100)
  - indicators (pola mencurigakan)
  - verified_claims (hasil verifikasi tiap klaim)
  - sources_found (URL sumber yang ditemukan)
  - verdict: KREDIBEL / PERLU DICEK / KEMUNGKINAN HOAKS
  - reasoning (penjelasan singkat)
        │
        ▼
Simpan ke Firestore → Tampil di Next.js Frontend
```

### Alur News Feed

```
Cloud Scheduler (setiap 1 jam)
        │
        ▼
Cloud Run Job fetch Google News RSS
(https://news.google.com/rss?hl=id&gl=ID&ceid=ID:id)
        │
        ▼
Gemini 2.0 Flash buat ringkasan batch
        │
        ▼
Cache hasil di Firestore (TTL 1 jam)
        │
        ▼
GET /news → Frontend tampilkan card berita
```

---

## 3. Tech Stack Lengkap

### Frontend

| Teknologi | Versi | Fungsi | Alasan Dipilih |
|---|---|---|---|
| **Next.js** | 14+ | Framework React utama | SSR untuk SEO, App Router, API Routes built-in |
| **React** | 18+ | UI library | Component-based, state management mudah |
| **Tailwind CSS** | 3+ | Styling | Utility-first, prototyping cepat |
| **TypeScript** | 5+ | Type safety | Mengurangi bug, autocomplete lebih baik |
| **Axios** | - | HTTP client | Request ke FastAPI backend |

### Backend

| Teknologi | Versi | Fungsi | Alasan Dipilih |
|---|---|---|---|
| **FastAPI** | 0.110+ | Framework API | Python async native, auto Swagger docs |
| **Python** | 3.11+ | Bahasa backend | Satu bahasa dengan AI SDK Gemini |
| **newspaper3k** | - | URL scraper | Ekstrak teks bersih dari artikel berita |
| **feedparser** | - | RSS parser | Ambil Google News RSS feed Indonesia |
| **httpx** | - | Async HTTP client | Request async ke layanan eksternal |
| **google-generativeai** | - | Gemini SDK | Integrasi Gemini API + Search Grounding |
| **google-cloud-firestore** | - | Firestore client | Simpan history & cache ke Firestore |
| **pydantic** | 2+ | Validasi data | Schema input/output API |
| **python-dotenv** | - | Env variables | Kelola konfigurasi lokal |

### AI & Search

| Teknologi | Fungsi | Catatan |
|---|---|---|
| **Gemini 2.0 Flash** | Model utama analisis | Cepat, murah, 1.500 req/hari gratis di AI Studio |
| **Google Search Grounding** | Verifikasi fakta real-time | Native di Gemini, aktifkan dengan `tools=["google_search"]` |
| **Gemini 2.5 Pro** | Analisis mendalam | Post-MVP, untuk artikel panjang atau kasus kompleks |
| **Vertex AI** | Fine-tuning model | Advanced, jika butuh model khusus hoaks Indonesia |

### Google Cloud Platform

| Layanan GCP | Fungsi | Free Tier |
|---|---|---|
| **Cloud Run** | Host Next.js + FastAPI sebagai container | 2 juta req/bulan · 360k vCPU-detik |
| **Artifact Registry** | Simpan Docker image | 0.5 GB/bulan |
| **Firestore** | Database history + cache | 50k read + 20k write/hari |
| **Cloud Storage** | Simpan gambar upload (post-MVP) | 5 GB/bulan |
| **Secret Manager** | Kelola API key Gemini | 6 secret gratis/bulan |
| **Cloud Scheduler** | Cron job news feed tiap jam | 3 job gratis/bulan |
| **Cloud Build** | CI/CD dari GitHub | 120 menit build/hari |
| **Cloud Monitoring** | Monitor latency & error | Gratis basic metrics |
| **Firebase Auth** | Autentikasi user (post-MVP) | 10k autentikasi/bulan |

### DevOps & Tools

| Tool | Fungsi |
|---|---|
| **Docker** | Kontainerisasi FastAPI & Next.js |
| **GitHub** | Version control + trigger Cloud Build |
| **cloudbuild.yaml** | Konfigurasi CI/CD pipeline |
| **Google AI Studio** | Management Gemini API key + playground |

---

## 4. Struktur Folder Project

```
hoax-detector/
│
├── frontend/                          # Next.js App
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx               # Halaman utama (input + hasil)
│   │   │   ├── news/
│   │   │   │   └── page.tsx           # Halaman news feed
│   │   │   ├── history/
│   │   │   │   └── page.tsx           # Riwayat analisis
│   │   │   ├── layout.tsx             # Root layout
│   │   │   └── globals.css            # Global styles
│   │   ├── components/
│   │   │   ├── AnalysisForm.tsx       # Form input teks/URL
│   │   │   ├── VerdictCard.tsx        # Badge + skor + penjelasan
│   │   │   ├── IndicatorList.tsx      # Daftar indikator mencurigakan
│   │   │   ├── SourcesList.tsx        # Sumber yang ditemukan Gemini
│   │   │   ├── NewsCard.tsx           # Card berita di news feed
│   │   │   ├── NewsFeed.tsx           # Grid news feed
│   │   │   └── LoadingSkeleton.tsx    # Loading state
│   │   ├── lib/
│   │   │   ├── api.ts                 # Fungsi request ke FastAPI
│   │   │   └── firebase.ts            # Firebase client config
│   │   └── types/
│   │       └── index.ts               # TypeScript types
│   ├── public/
│   ├── Dockerfile                     # Docker untuk Next.js
│   ├── next.config.js
│   ├── tailwind.config.js
│   └── package.json
│
├── backend/                           # FastAPI App
│   ├── app/
│   │   ├── main.py                    # Entry point FastAPI
│   │   ├── routers/
│   │   │   ├── analyze.py             # POST /analyze
│   │   │   └── news.py                # GET /news
│   │   ├── services/
│   │   │   ├── gemini_service.py      # Logika Gemini API + Grounding
│   │   │   ├── scraper_service.py     # URL scraping dengan newspaper3k
│   │   │   ├── news_service.py        # Fetch + parse Google News RSS
│   │   │   └── firestore_service.py   # CRUD ke Firestore
│   │   ├── models/
│   │   │   ├── request_models.py      # Pydantic request schema
│   │   │   └── response_models.py     # Pydantic response schema
│   │   └── config.py                  # Konfigurasi environment
│   ├── Dockerfile                     # Docker untuk FastAPI
│   ├── requirements.txt
│   └── .env.example
│
├── infra/                             # Konfigurasi GCP
│   ├── cloudbuild.yaml                # CI/CD pipeline
│   ├── cloud-run-frontend.yaml        # Cloud Run config Next.js
│   ├── cloud-run-backend.yaml         # Cloud Run config FastAPI
│   └── scheduler-job.yaml             # Cloud Scheduler config
│
└── README.md
```

---

## 5. AI & Gemini API

### Cara Aktifkan Google Search Grounding

```python
# backend/app/services/gemini_service.py

import google.generativeai as genai
import json
import os

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    tools=["google_search"]  # ← Aktifkan Search Grounding
)

async def analyze_hoax(text: str) -> dict:
    prompt = build_prompt(text)
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)
```

### Prompt Final (Dioptimasi untuk Konteks Indonesia)

```
Kamu adalah fact-checker profesional yang berspesialisasi pada 
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
{input_user}
```

### Aturan Scoring

| Skor | Verdict | Kondisi |
|---|---|---|
| 75 – 100 | `KREDIBEL` | Klaim terkonfirmasi dari sumber terpercaya, tidak ada indikator hoaks |
| 40 – 74 | `PERLU DICEK` | Klaim sebagian terkonfirmasi, ada beberapa indikator meragukan |
| 0 – 39 | `KEMUNGKINAN HOAKS` | Klaim dibantah atau tidak terverifikasi, banyak indikator hoaks |

---

## 6. Infrastruktur GCP

### Overview Layanan

```
GitHub Repo
     │
     │ push ke main
     ▼
Cloud Build (CI/CD)
     │
     ├──► Build Docker image Next.js
     │         │
     │         ▼
     │    Artifact Registry
     │         │
     │         ▼
     │    Cloud Run (Next.js)  ◄─── User traffic
     │
     └──► Build Docker image FastAPI
               │
               ▼
          Artifact Registry
               │
               ▼
          Cloud Run (FastAPI)
               │
               ├── Gemini API (AI Studio)
               ├── Firestore
               └── Secret Manager (API keys)

Cloud Scheduler ──► Cloud Run Job (news fetch tiap jam)
```

### Konfigurasi Cloud Run — Frontend (Next.js)

```yaml
# infra/cloud-run-frontend.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hoax-detector-frontend
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "5"
    spec:
      containers:
        - image: asia-southeast1-docker.pkg.dev/PROJECT_ID/hoax-detector/frontend:latest
          ports:
            - containerPort: 3000
          env:
            - name: NEXT_PUBLIC_API_URL
              value: "https://hoax-detector-backend-xxxx-as.a.run.app"
          resources:
            limits:
              cpu: "1"
              memory: "512Mi"
```

### Konfigurasi Cloud Run — Backend (FastAPI)

```yaml
# infra/cloud-run-backend.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hoax-detector-backend
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "3"
    spec:
      serviceAccountName: hoax-detector-sa@PROJECT_ID.iam.gserviceaccount.com
      containers:
        - image: asia-southeast1-docker.pkg.dev/PROJECT_ID/hoax-detector/backend:latest
          ports:
            - containerPort: 8000
          env:
            - name: GEMINI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: gemini-api-key
                  key: latest
            - name: GCP_PROJECT_ID
              value: "PROJECT_ID"
          resources:
            limits:
              cpu: "1"
              memory: "512Mi"
```

### Dockerfile — Next.js

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
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

### Dockerfile — FastAPI

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Perintah Deploy Manual (Pertama Kali)

```bash
# 1. Setup project GCP
gcloud projects create hoax-detector-id
gcloud config set project hoax-detector-id

# 2. Aktifkan layanan yang dibutuhkan
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com

# 3. Buat Artifact Registry
gcloud artifacts repositories create hoax-detector \
  --repository-format=docker \
  --location=asia-southeast1

# 4. Simpan Gemini API key ke Secret Manager
echo -n "YOUR_GEMINI_API_KEY" | \
  gcloud secrets create gemini-api-key --data-file=-

# 5. Build & push image Backend
cd backend
gcloud builds submit --tag \
  asia-southeast1-docker.pkg.dev/hoax-detector-id/hoax-detector/backend:latest

# 6. Deploy Backend ke Cloud Run
gcloud run deploy hoax-detector-backend \
  --image asia-southeast1-docker.pkg.dev/hoax-detector-id/hoax-detector/backend:latest \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest

# 7. Build & push image Frontend
cd ../frontend
gcloud builds submit --tag \
  asia-southeast1-docker.pkg.dev/hoax-detector-id/hoax-detector/frontend:latest

# 8. Deploy Frontend ke Cloud Run
gcloud run deploy hoax-detector-frontend \
  --image asia-southeast1-docker.pkg.dev/hoax-detector-id/hoax-detector/frontend:latest \
  --region asia-southeast1 \
  --allow-unauthenticated

# 9. Setup Firestore
gcloud firestore databases create --region=asia-southeast1

# 10. Setup Cloud Scheduler untuk news feed
gcloud scheduler jobs create http news-feed-scheduler \
  --location=asia-southeast1 \
  --schedule="0 * * * *" \
  --uri="https://hoax-detector-backend-xxxx-as.a.run.app/news/refresh" \
  --http-method=POST
```

---

## 7. CI/CD Pipeline

### cloudbuild.yaml

```yaml
# infra/cloudbuild.yaml
steps:
  # ─── Backend ───────────────────────────────────────────────
  - name: "gcr.io/cloud-builders/docker"
    args:
      - build
      - -t
      - asia-southeast1-docker.pkg.dev/$PROJECT_ID/hoax-detector/backend:$COMMIT_SHA
      - ./backend
    id: "build-backend"

  - name: "gcr.io/cloud-builders/docker"
    args:
      - push
      - asia-southeast1-docker.pkg.dev/$PROJECT_ID/hoax-detector/backend:$COMMIT_SHA
    id: "push-backend"
    waitFor: ["build-backend"]

  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    entrypoint: gcloud
    args:
      - run
      - deploy
      - hoax-detector-backend
      - --image=asia-southeast1-docker.pkg.dev/$PROJECT_ID/hoax-detector/backend:$COMMIT_SHA
      - --region=asia-southeast1
      - --allow-unauthenticated
    id: "deploy-backend"
    waitFor: ["push-backend"]

  # ─── Frontend ──────────────────────────────────────────────
  - name: "gcr.io/cloud-builders/docker"
    args:
      - build
      - -t
      - asia-southeast1-docker.pkg.dev/$PROJECT_ID/hoax-detector/frontend:$COMMIT_SHA
      - ./frontend
    id: "build-frontend"

  - name: "gcr.io/cloud-builders/docker"
    args:
      - push
      - asia-southeast1-docker.pkg.dev/$PROJECT_ID/hoax-detector/frontend:$COMMIT_SHA
    id: "push-frontend"
    waitFor: ["build-frontend"]

  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    entrypoint: gcloud
    args:
      - run
      - deploy
      - hoax-detector-frontend
      - --image=asia-southeast1-docker.pkg.dev/$PROJECT_ID/hoax-detector/frontend:$COMMIT_SHA
      - --region=asia-southeast1
      - --allow-unauthenticated
    id: "deploy-frontend"
    waitFor: ["push-frontend"]

options:
  logging: CLOUD_LOGGING_ONLY
```

### Setup Trigger dari GitHub

```bash
# Hubungkan GitHub repo ke Cloud Build
gcloud builds triggers create github \
  --name="hoax-detector-deploy" \
  --repo-name="hoax-detector" \
  --repo-owner="YOUR_GITHUB_USERNAME" \
  --branch-pattern="^main$" \
  --build-config="infra/cloudbuild.yaml"
```

---

## 8. Fitur Aplikasi

### MVP (Hari 1–3)

| No | Fitur | Endpoint | Status |
|---|---|---|---|
| 1 | Input teks berita | `POST /analyze` | MVP |
| 2 | Input URL artikel | `POST /analyze` + scraper | MVP |
| 3 | Skor kepercayaan 0–100 | Respons JSON | MVP |
| 4 | Badge verdict berwarna | Frontend component | MVP |
| 5 | Daftar indikator mencurigakan | Respons JSON | MVP |
| 6 | Sumber verifikasi yang ditemukan | Respons JSON | MVP |
| 7 | News feed berita Indonesia | `GET /news` | MVP |
| 8 | Ringkasan AI per berita | Batch Gemini | MVP |
| 9 | Klik berita → analisis langsung | Frontend routing | MVP |

### Post-MVP (Minggu 2)

| No | Fitur | Komponen | Status |
|---|---|---|---|
| 10 | History analisis tersimpan | Firestore | Post-MVP |
| 11 | Share hasil via URL unik | Firestore + routing | Post-MVP |
| 12 | Integrasi Turnbackhoax.id | RSS scraper | Post-MVP |
| 13 | Integrasi Cekfakta.com | RSS scraper | Post-MVP |
| 14 | Quick verdict di news feed | Batch analyze | Post-MVP |

### Advanced (Bulan 2+)

| No | Fitur | Komponen | Status |
|---|---|---|---|
| 15 | Analisis gambar/foto | Gemini Vision | Advanced |
| 16 | Login user (Google Auth) | Firebase Auth | Advanced |
| 17 | Dashboard statistik personal | Firestore + Chart | Advanced |
| 18 | Fine-tuning model hoaks Indonesia | Vertex AI | Advanced |
| 19 | API publik untuk developer | FastAPI + API key | Advanced |

---

## 9. Rencana Pengembangan

### Hari 1 — Backend & AI

```
[ ] Setup GCP project + aktifkan semua layanan
[ ] Daftarkan Google AI Studio + generate Gemini API key
[ ] Simpan API key ke Secret Manager
[ ] Inisialisasi FastAPI project (struktur folder)
[ ] Implementasi POST /analyze dengan Gemini + Search Grounding
[ ] Implementasi URL scraper (newspaper3k)
[ ] Implementasi GET /news dari Google News RSS
[ ] Test semua endpoint via Swagger UI (localhost)
[ ] Buat Dockerfile untuk FastAPI
[ ] Push image ke Artifact Registry
[ ] Deploy backend ke Cloud Run
```

### Hari 2 — Frontend & Integrasi

```
[ ] Inisialisasi Next.js project (TypeScript + Tailwind)
[ ] Komponen AnalysisForm (input teks + URL)
[ ] Komponen VerdictCard (badge + skor)
[ ] Komponen IndicatorList (daftar indikator)
[ ] Komponen SourcesList (sumber verifikasi)
[ ] Komponen NewsFeed + NewsCard
[ ] Integrasi frontend → Cloud Run backend URL
[ ] Buat Dockerfile untuk Next.js
[ ] Push image ke Artifact Registry
[ ] Deploy frontend ke Cloud Run
```

### Hari 3 — CI/CD, Polish & Launch

```
[ ] Setup cloudbuild.yaml
[ ] Hubungkan GitHub repo ke Cloud Build trigger
[ ] Test CI/CD: push ke main → auto deploy
[ ] Setup Firestore koleksi untuk history
[ ] Setup Cloud Scheduler untuk news feed
[ ] CORS configuration
[ ] Error handling + loading state
[ ] Mobile responsive check
[ ] Smoke test end-to-end (teks, URL, news feed)
[ ] (Opsional) Custom domain di Cloud Run
```

### Minggu 2 — Post-MVP

```
[ ] Integrasi Turnbackhoax RSS ke pipeline analisis
[ ] Integrasi Cekfakta.com RSS
[ ] Halaman history analisis (Firestore)
[ ] Fitur share hasil (URL unik)
[ ] Quick verdict otomatis di news feed
[ ] Cloud Monitoring alert setup
```

---

## 10. Estimasi Biaya GCP

### Fase MVP (Traffic Rendah, < 1.000 req/hari)

| Layanan | Penggunaan | Biaya |
|---|---|---|
| Cloud Run (Frontend) | < 2 juta req/bulan | **Gratis** |
| Cloud Run (Backend) | < 2 juta req/bulan | **Gratis** |
| Artifact Registry | < 0.5 GB | **Gratis** |
| Firestore | < 50k read + 20k write/hari | **Gratis** |
| Secret Manager | < 6 secrets | **Gratis** |
| Cloud Scheduler | < 3 jobs | **Gratis** |
| Cloud Build | < 120 menit/hari | **Gratis** |
| **Gemini API** | 1.500 req/hari (AI Studio) | **Gratis** |
| **Total** | | **Rp 0 / bulan** |

### Fase Growth (Traffic Sedang, 10.000–50.000 req/hari)

| Layanan | Estimasi Biaya |
|---|---|
| Cloud Run (2 service) | ~$5–15/bulan |
| Firestore (lebih dari free tier) | ~$1–5/bulan |
| Gemini API (pay-as-you-go) | ~$10–30/bulan |
| Artifact Registry | ~$1/bulan |
| **Total Estimasi** | **~$17–51/bulan (~Rp 270rb–800rb)** |

> **Catatan:** Upgrade dari AI Studio ke Gemini API via Google Cloud (Vertex AI) jika sudah melewati batas 1.500 req/hari gratis. Harga Gemini 2.0 Flash sekitar $0.075 per 1 juta token input.

---

## Referensi

- [Google AI Studio](https://aistudio.google.com) — Manage Gemini API key & playground
- [Gemini API Docs](https://ai.google.dev/docs) — Dokumentasi resmi Gemini
- [Google Search Grounding](https://ai.google.dev/gemini-api/docs/grounding) — Cara kerja Search Grounding
- [Cloud Run Docs](https://cloud.google.com/run/docs) — Deploy container ke Cloud Run
- [Firestore Docs](https://cloud.google.com/firestore/docs) — NoSQL database GCP
- [Cloud Build Docs](https://cloud.google.com/build/docs) — CI/CD pipeline
- [Turnbackhoax.id](https://turnbackhoax.id) — Database hoaks Indonesia
- [Cekfakta.com](https://cekfakta.com) — Fact-checking Indonesia

---

*Dokumen ini dibuat sebagai panduan pengembangan Aplikasi AI Pendeteksi Hoaks.*  
*Terakhir diperbarui: 2025*
