# Panduan Membuat Fitur Login (Firebase Auth) dari Awal

> Dokumentasi lengkap sesi penambahan fitur login Google ke aplikasi **Faktain (Anti-Hoax)**.
> Ditulis sebagai bahan belajar: setiap keputusan, perintah, dan file dijelaskan detail.

---

## Daftar Isi

1. [Tujuan & Keputusan Desain](#1-tujuan--keputusan-desain)
2. [Gambaran Arsitektur](#2-gambaran-arsitektur)
3. [Prasyarat](#3-prasyarat)
4. [Semua Perintah (Command) yang Dijalankan](#4-semua-perintah-command-yang-dijalankan)
5. [Implementasi Backend (FastAPI)](#5-implementasi-backend-fastapi)
6. [Implementasi Frontend (Next.js)](#6-implementasi-frontend-nextjs)
7. [Cara Kerja End-to-End](#7-cara-kerja-end-to-end)
8. [Setup Firebase (Wajib agar Login Muncul)](#8-setup-firebase-wajib-agar-login-muncul)
9. [Cara Menguji](#9-cara-menguji)
10. [Daftar File yang Dibuat/Diubah](#10-daftar-file-yang-dibuatdiubah)
11. [Catatan untuk Belajar & Pengembangan Lanjutan](#11-catatan-untuk-belajar--pengembangan-lanjutan)

---

## 1. Tujuan & Keputusan Desain

### Masalah awal
Permintaan awalnya: "tambahkan login jika ingin mengakses fitur verifikasi berita."

### Mengapa **tidak** menggunakan gate penuh (wajib login)
Aplikasi ini adalah alat cek fakta untuk publik. Kekuatan utamanya ada di **friksi rendah** — orang menemukan pesan berantai mencurigakan, langsung tempel, langsung cek. Kalau verifikasi dikunci di balik login, sebagian besar nilai itu hilang karena orang enggan mendaftar hanya untuk mengecek satu klaim.

### Keputusan: **Login opsional + rate limit**
| Tipe pengguna | Bisa verifikasi? | Kuota | Cara dibatasi |
|---|---|---|---|
| Anonim (tamu) | Ya | Rendah (default 5/jam) | Per alamat IP |
| Login (Google) | Ya | Tinggi (default 50/jam) | Per UID pengguna |

Pendekatan ini menyelesaikan masalah nyata (**biaya & penyalahgunaan endpoint AI**) tanpa membunuh misi publik aplikasi.

### Mengapa Firebase Auth
- Sudah disebut di dokumen tech stack project (`Firebase Auth — 10k autentikasi/bulan gratis`).
- Tidak perlu menjalankan server auth sendiri.
- Google sign-in populer & cepat untuk pengguna Indonesia.
- Backend cukup memverifikasi **ID token** (JWT) yang dikirim frontend.

### Prinsip penting: keamanan tidak boleh hanya di frontend
Menyembunyikan tombol di UI **bukan** keamanan. Orang tetap bisa memanggil API `/analyze` langsung (misal lewat `curl`). Karena itu **backend wajib ikut memverifikasi token** dan menerapkan rate limit. Itulah kenapa pekerjaan ini menyentuh backend dan frontend sekaligus.

---

## 2. Gambaran Arsitektur

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Next.js)                         │
│                                                              │
│  [Tombol Masuk] ──klik──► Firebase Auth (popup Google)       │
│         │                        │                           │
│         │                        ▼                           │
│         │                 ID Token (JWT)                     │
│         │                        │                           │
│         ▼                        ▼                           │
│  AuthProvider ──simpan token──► axios interceptor            │
│                                  │                           │
└──────────────────────────────────┼──────────────────────────┘
                                    │ Authorization: Bearer <token>
                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                        │
│                                                              │
│  Dependency: get_current_user                                │
│    └─► auth_service.verify_id_token(token)                   │
│          └─► verifikasi tanda tangan JWT pakai cert Google   │
│                                                              │
│  Dependency: enforce_analyze_rate_limit                      │
│    ├─ login  → batasi per UID  (kuota tinggi)                │
│    └─ anonim → batasi per IP   (kuota rendah)                │
│                                                              │
│  Jika lolos → jalankan analisis hoaks                        │
│  Jika kuota habis → 429 Too Many Requests + Retry-After      │
└─────────────────────────────────────────────────────────────┘
```

**Inti yang perlu dipahami:** token dibuat oleh Firebase di sisi browser, lalu dikirim ke backend di header `Authorization`. Backend tidak pernah memegang password; ia hanya memverifikasi bahwa token itu asli (ditandatangani Google) dan belum kedaluwarsa.

---

## 3. Prasyarat

- Node.js + npm (untuk frontend Next.js).
- Python 3.10+ (untuk backend FastAPI).
- Akun Google (untuk membuat project Firebase) — diperlukan **hanya saat ingin login benar-benar aktif**.

---

## 4. Semua Perintah (Command) yang Dijalankan

Berikut **semua** perintah yang dijalankan selama sesi, beserta tujuannya. Lokasi kerja ditandai dengan `cwd`.

### 4.1 Cek apakah dependency JWT sudah ada (backend)
```powershell
# cwd: d:\Project\anti-hoax\backend
python -c "import jwt, cryptography; print('jwt', jwt.__version__); print('crypto ok')"
```
**Tujuan:** memeriksa apakah library `PyJWT` dan `cryptography` sudah terpasang.
**Hasil:** `ModuleNotFoundError: No module named 'jwt'` → berarti `PyJWT` belum ada, perlu diinstal.

### 4.2 Instal dependency backend untuk verifikasi token
```powershell
# cwd: d:\Project\anti-hoax\backend
python -m pip install PyJWT==2.9.0 cryptography==43.0.1
```
**Tujuan:**
- `PyJWT` → membaca & memverifikasi token JWT (format token Firebase).
- `cryptography` → menyediakan algoritma RSA untuk memvalidasi tanda tangan token.

### 4.3 Verifikasi semua modul backend baru bisa diimpor
```powershell
# cwd: d:\Project\anti-hoax\backend
python -c "from app.dependencies import enforce_analyze_rate_limit, get_current_user; from app.services import auth_service, rate_limit_service; from app.routers import analyze; print('all imports OK; auth enabled =', auth_service.is_enabled())"
```
**Tujuan:** memastikan tidak ada salah ketik/import yang membuat aplikasi gagal start.

### 4.4 Uji cepat logika rate limiter & status auth
```powershell
# cwd: d:\Project\anti-hoax\backend
python -c "from app.services.rate_limit_service import FixedWindowRateLimiter; rl=FixedWindowRateLimiter(60); res=[rl.check('ip:x',3) for _ in range(4)]; print([(r.allowed,r.remaining) for r in res]); from app.config import settings; print('auth enabled (should be False):', bool(settings.FIREBASE_PROJECT_ID))"
```
**Tujuan:** memastikan limiter benar (3 permintaan pertama lolos, ke-4 ditolak) dan auth default ke mode anonim saat `FIREBASE_PROJECT_ID` kosong.
**Hasil:** `[(True, 2), (True, 1), (True, 0), (False, 0)]` dan `auth enabled: False`. ✅

### 4.5 Instal Firebase SDK (frontend)
```powershell
# cwd: d:\Project\anti-hoax\frontend
npm install firebase@^11.1.0
```
**Tujuan:** menambahkan Firebase Web SDK untuk login Google di browser.

### 4.6 Build frontend untuk memastikan semua kompilasi
```powershell
# cwd: d:\Project\anti-hoax\frontend
npm run build
```
**Tujuan:** memastikan integrasi Firebase + perubahan TypeScript/React tidak ada error.
**Hasil:** build sukses, semua route ter-render. ✅

### 4.7 Verifikasi aplikasi FastAPI lengkap bisa diimpor
```powershell
# cwd: d:\Project\anti-hoax\backend
python -c "from app.main import app; routes=[r.path for r in app.routes]; print('analyze in routes:', '/analyze' in routes); print('OK')"
```
**Tujuan:** memastikan router `/analyze` (yang sekarang memakai dependency baru) tetap terdaftar dan app bisa dijalankan.

### 4.8 Uji end-to-end rate limit lewat TestClient
File uji sementara `_test_ratelimit.py` dibuat, lalu dijalankan:
```powershell
# cwd: d:\Project\anti-hoax\backend
python _test_ratelimit.py
```
**Tujuan:** membuktikan bahwa pada `/analyze`, dependency rate limit berjalan **sebelum** logika analisis, dan pengguna anonim dibatasi 5x lalu mendapat 429.
**Hasil:** `statuses: [400, 400, 400, 400, 400, 429, 429]` → `PASS`. ✅
File uji ini **dihapus** setelah selesai (hanya alat bantu verifikasi).

> Catatan platform: shell yang dipakai adalah **PowerShell di Windows**. Pemisah perintah memakai `;` (bukan `&&`). Perintah `python -c "..."` ditulis satu baris.

---

## 5. Implementasi Backend (FastAPI)

Backend punya 3 tanggung jawab baru: **(a)** verifikasi token, **(b)** rate limit, **(c)** menyambungkan keduanya ke endpoint `/analyze`.

### 5.1 `app/config.py` — tambah konfigurasi

Ditambahkan pengaturan Firebase & rate limit. Bagian penting:

```python
class Settings:
    # ...
    # Firebase Auth (opsional). Kalau FIREBASE_PROJECT_ID kosong → mode anonim.
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    # Rate limit untuk /analyze (fixed window).
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 jam
    ANON_RATE_LIMIT: int = int(os.getenv("ANON_RATE_LIMIT", "5"))
    USER_RATE_LIMIT: int = int(os.getenv("USER_RATE_LIMIT", "50"))
```

**Penjelasan belajar:**
- `os.getenv("X", "default")` membaca variabel lingkungan; kalau tidak ada, pakai default.
- **Penting:** `FIREBASE_PROJECT_ID` sengaja **tidak** otomatis mengambil nilai `GCP_PROJECT_ID`. Awalnya sempat begitu, tapi karena `.env` berisi placeholder `your_gcp_project_id`, auth jadi "seolah aktif" lalu menolak semua token asli. Membuatnya eksplisit mencegah jebakan ini.

### 5.2 `app/services/auth_service.py` — verifikasi ID token

Tugasnya: menerima string token dari frontend, lalu memastikan token itu **asli** dan **valid**.

Cara kerja verifikasi JWT Firebase:
1. Token JWT punya 3 bagian: `header.payload.signature`.
2. Dari `header` kita ambil `kid` (key id) → menunjuk sertifikat mana yang dipakai menandatangani.
3. Ambil sertifikat publik Google (di-cache, menghormati `Cache-Control: max-age`).
4. Verifikasi tanda tangan + cek `audience` (harus = project id) + `issuer` (harus = `https://securetoken.google.com/<project_id>`) + masa berlaku.
5. Kalau lolos → ambil `uid`, `email`, `name` dari payload.

Inti kodenya:
```python
def is_enabled() -> bool:
    """True kalau verifikasi Firebase dikonfigurasi."""
    return bool(settings.FIREBASE_PROJECT_ID)

async def verify_id_token(id_token: str) -> AuthUser:
    # ambil 'kid' dari header → cari sertifikat Google yang cocok
    # decode + verifikasi tanda tangan, audience, issuer, expiry
    # kembalikan AuthUser(uid, email, name)
```

**Mengapa tidak pakai `firebase-admin`?**
SDK resmi `firebase-admin` itu besar dan menyeret banyak dependency. Karena kita hanya butuh **memverifikasi token**, cukup pakai `PyJWT` + `cryptography` yang ringan. Ini pola umum dan tetap aman karena memakai sertifikat publik resmi Google.

**Sifat opsional:** kalau `FIREBASE_PROJECT_ID` kosong, `is_enabled()` → `False`, dan pemanggil akan menganggap request sebagai anonim (tanpa error). Ini membuat pengembangan lokal tetap lancar tanpa setup Firebase.

### 5.3 `app/services/rate_limit_service.py` — pembatas laju

Implementasi **fixed-window rate limiter** di memori:
- Menyimpan daftar timestamp per "key" (key = `ip:1.2.3.4` atau `user:<uid>`).
- Saat ada request, buang timestamp yang lebih tua dari window, lalu hitung sisa.
- Kalau jumlah dalam window ≥ limit → tolak, sambil menghitung `reset_after` (berapa detik lagi boleh coba).

```python
@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after: int  # detik sampai window reset
```

**Penjelasan belajar:**
- "Fixed window" = jendela waktu tetap (mis. 1 jam). Sederhana dan cukup untuk kebutuhan ini.
- Pakai `threading.Lock()` agar aman saat banyak request bersamaan.
- **Keterbatasan:** state ada di memori satu proses. Kalau aplikasi diskalakan ke banyak instance (mis. Cloud Run autoscale), tiap instance punya hitungan sendiri. Untuk produksi multi-instance, ganti ke store bersama (Firestore/Redis). API-nya sengaja dibuat kecil agar mudah ditukar.

### 5.4 `app/dependencies.py` — penyatu auth + rate limit

FastAPI punya konsep **dependency injection**: fungsi yang dijalankan otomatis sebelum handler endpoint. Di sini ada dua:

```python
async def get_current_user(request: Request) -> Optional[AuthUser]:
    # Baca header "Authorization: Bearer <token>".
    # - Tidak ada token        → None (anonim).
    # - Ada token, auth nonaktif → None (anggap anonim).
    # - Ada token, valid       → AuthUser.
    # - Ada token, TIDAK valid  → HTTP 401 (biar user tahu harus login ulang).

async def enforce_analyze_rate_limit(request, user=Depends(get_current_user)):
    # Pilih kunci & limit:
    #   login  → key "user:<uid>", limit USER_RATE_LIMIT
    #   anonim → key "ip:<client_ip>", limit ANON_RATE_LIMIT
    # Kalau habis → HTTP 429 + header Retry-After.
```

**Penjelasan belajar:**
- `Depends(get_current_user)` artinya `enforce_analyze_rate_limit` "meminta" hasil `get_current_user` lebih dulu — FastAPI merangkainya otomatis.
- IP klien diambil dari header `X-Forwarded-For` (di-set oleh proxy/Cloud Run), fallback ke `request.client.host`.
- Status **429 Too Many Requests** + header **`Retry-After`** adalah standar HTTP untuk "coba lagi nanti".

### 5.5 `app/routers/analyze.py` — pasang dependency

Perubahan kunci: endpoint sekarang menerima hasil dependency.
```python
@router.post("", response_model=AnalysisResponse)
async def analyze_content(
    request: AnalyzeRequest,
    user: Optional[AuthUser] = Depends(enforce_analyze_rate_limit),
):
    ...
```
Karena `enforce_analyze_rate_limit` dipasang sebagai dependency, **rate limit & auth otomatis dijalankan sebelum** logika analisis. Kalau kuota habis, handler bahkan tidak akan dieksekusi.

### 5.6 `requirements.txt` & `.env` / `.env.example`

`requirements.txt` ditambah:
```
PyJWT==2.9.0
cryptography==43.0.1
```

`.env` & `.env.example` ditambah blok:
```dotenv
# Firebase Auth (opsional) — kosongkan untuk mode anonim
FIREBASE_PROJECT_ID=
GOOGLE_APPLICATION_CREDENTIALS=

# Rate limiting untuk /analyze
RATE_LIMIT_WINDOW=3600
ANON_RATE_LIMIT=5
USER_RATE_LIMIT=50
```

---

## 6. Implementasi Frontend (Next.js)

Frontend bertugas: **menyediakan tombol login**, **menyimpan sesi**, dan **melampirkan token** ke setiap panggilan API.

### 6.1 `src/lib/firebase.ts` — konfigurasi klien Firebase

```typescript
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export function isAuthConfigured(): boolean {
  return Boolean(firebaseConfig.apiKey && firebaseConfig.authDomain);
}
```

**Penjelasan belajar:**
- Prefix `NEXT_PUBLIC_` membuat variabel bisa dibaca di **browser**. Nilai config Firebase memang **bukan rahasia** — keamanan diatur oleh Firebase Rules & pengaturan Auth, bukan dengan menyembunyikan apiKey.
- `isAuthConfigured()` adalah **saklar utama**: kalau env kosong → seluruh UI login disembunyikan dan app jalan mode anonim. **Inilah alasan tombol login belum muncul sampai env diisi.**

### 6.2 `src/components/AuthProvider.tsx` — konteks auth global

Komponen ini membungkus seluruh aplikasi (via layout) dan menyediakan:
- `user` — pengguna yang sedang login (atau `null`).
- `loading` — saat status auth awal masih dimuat.
- `signInWithGoogle()` & `signOut()`.
- Menyuntikkan fungsi pengambil token ke layer axios via `setTokenProvider(...)`.

```typescript
useEffect(() => {
  setTokenProvider(async () => {
    if (!firebaseAuth?.currentUser) return null;
    return await firebaseAuth.currentUser.getIdToken();
  });
  return () => setTokenProvider(null);
}, []);
```

**Penjelasan belajar:**
- React **Context** dipakai agar komponen mana pun bisa tahu status login tanpa "prop drilling".
- `onAuthStateChanged` adalah listener Firebase yang otomatis terpanggil saat user login/logout/refresh halaman — jadi sesi tetap konsisten.
- Pemisahan token via `setTokenProvider` membuat `lib/api.ts` **tidak perlu meng-import Firebase**. Ini menjaga kode tetap modular (loose coupling).

### 6.3 `src/lib/api.ts` — lampirkan token otomatis

```typescript
let tokenProvider: TokenProvider | null = null;
export function setTokenProvider(provider: TokenProvider | null) {
  tokenProvider = provider;
}

api.interceptors.request.use(async (config) => {
  if (tokenProvider) {
    const token = await tokenProvider();
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

**Penjelasan belajar:**
- **Interceptor** axios = "penyadap" yang berjalan sebelum tiap request dikirim. Di sini kita pakai untuk menempelkan `Authorization: Bearer <token>` secara otomatis, sehingga setiap pemanggil (`analyzeText`, dll.) tidak perlu memikirkan token.

### 6.4 `src/components/AuthButton.tsx` — tombol di header

```typescript
if (!authConfigured) return null;      // ← sembunyikan kalau Firebase belum diset
if (loading) return <span>…</span>;
if (user) return <>{nama} [Keluar]</>; // sudah login
return <button onClick={signInWithGoogle}>Masuk</button>;
```

**Penjelasan belajar:** komponen ini "self-aware" — ia tahu kapan harus menampilkan "Masuk", nama pengguna, atau tidak sama sekali. Guard `if (!authConfigured) return null` inilah yang menyembunyikan tombol saat env kosong.

### 6.5 `src/app/layout.tsx` — pasang provider & tombol

- Membungkus seluruh isi dengan `<AuthProvider>`.
- Mengganti teks "Jakarta, Indonesia" di utility bar dengan `<AuthButton />`.

```tsx
<body>
  <AuthProvider>
    ...
    <AuthButton />
    ...
  </AuthProvider>
</body>
```

### 6.6 `src/app/verifikasi/page.tsx` — banner & penanganan error

- Menambahkan **banner ajakan login** untuk tamu (`authConfigured && !user`).
- Menangani error spesifik:
  - **429** → tampilkan pesan batas analisis tercapai (dari backend, sudah berisi saran login).
  - **401** → "Sesi login berakhir. Silakan masuk kembali."

### 6.7 `frontend/.env.local` — variabel (masih kosong)

```dotenv
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
```
> **Inilah sebabnya fitur login belum tampil.** Lihat bagian 8 untuk mengisinya.

---

## 7. Cara Kerja End-to-End

1. Pengguna klik **Masuk** → Firebase membuka popup Google → setelah berhasil, Firebase menyimpan sesi di browser.
2. `AuthProvider` mendeteksi perubahan via `onAuthStateChanged`, lalu menaruh fungsi pengambil token ke axios.
3. Saat pengguna menekan **Analisis**, axios interceptor mengambil ID token terbaru dan menempelkannya: `Authorization: Bearer <token>`.
4. Backend (`get_current_user`) memverifikasi token → tahu siapa pengguna (UID).
5. `enforce_analyze_rate_limit` menerapkan kuota: per UID untuk yang login, per IP untuk anonim.
6. Kalau lolos → analisis berjalan. Kalau habis → balas **429** dengan `Retry-After`.
7. Frontend menampilkan pesan error yang sesuai (429/401/lainnya).

---

## 8. Setup Firebase (Wajib agar Login Muncul)

Tanpa langkah ini, aplikasi tetap berjalan **mode anonim** dan tombol login disembunyikan.

1. Buka [Firebase Console](https://console.firebase.google.com) → **Add project** (atau pakai project GCP yang sudah ada).
2. **Authentication** → **Get started** → tab **Sign-in method** → aktifkan **Google** → Save.
3. **Project settings** (ikon gerigi) → scroll ke **Your apps** → klik ikon **Web (`</>`)** → daftarkan app → salin objek `firebaseConfig`.
4. Isi `frontend/.env.local`:
   ```dotenv
   NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSy...
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=nama-project.firebaseapp.com
   NEXT_PUBLIC_FIREBASE_PROJECT_ID=nama-project
   NEXT_PUBLIC_FIREBASE_APP_ID=1:1234567890:web:abc123
   ```
5. Isi `backend/.env`:
   ```dotenv
   FIREBASE_PROJECT_ID=nama-project
   ```
   (harus **sama** dengan `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, karena dipakai memverifikasi `audience` token.)
6. **Authentication** → **Settings** → **Authorized domains** → pastikan `localhost` ada (untuk dev).
7. **Restart** dev server frontend. Variabel `NEXT_PUBLIC_*` hanya dibaca saat start — tidak hot-reload.

Setelah ini tombol **Masuk** muncul di utility bar dan banner login muncul di halaman verifikasi.

---

## 9. Cara Menguji

### Menjalankan backend (dev)
```powershell
# cwd: d:\Project\anti-hoax\backend
uvicorn app.main:app --reload --port 8000
```

### Menjalankan frontend (dev)
```powershell
# cwd: d:\Project\anti-hoax\frontend
npm run dev
```
> Jalankan perintah dev server ini **manual di terminal Anda**, karena prosesnya berjalan terus (long-running).

### Skenario uji
1. **Mode anonim** (env Firebase kosong): tombol login tidak tampil. Lakukan analisis berkali-kali → setelah melewati `ANON_RATE_LIMIT`, muncul pesan batas tercapai (429).
2. **Mode login** (env terisi): klik **Masuk** → login Google → nama muncul di header → kuota mengikuti `USER_RATE_LIMIT`.
3. **Uji backend langsung** (membuktikan UI bukan satu-satunya pengaman):
   ```powershell
   # Memanggil API tanpa lewat UI; tetap kena rate limit
   curl.exe -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d "{}"
   ```

---

## 10. Daftar File yang Dibuat/Diubah

### Backend
| File | Status | Fungsi |
|---|---|---|
| `backend/app/services/auth_service.py` | **baru** | Verifikasi Firebase ID token (PyJWT + cert Google) |
| `backend/app/services/rate_limit_service.py` | **baru** | Fixed-window rate limiter di memori |
| `backend/app/dependencies.py` | **baru** | Dependency `get_current_user` + `enforce_analyze_rate_limit` |
| `backend/app/config.py` | diubah | Tambah setting Firebase & rate limit |
| `backend/app/routers/analyze.py` | diubah | Pasang dependency rate limit ke `/analyze` |
| `backend/requirements.txt` | diubah | Tambah `PyJWT`, `cryptography` |
| `backend/.env` & `.env.example` | diubah | Tambah variabel Firebase & rate limit |

### Frontend
| File | Status | Fungsi |
|---|---|---|
| `frontend/src/lib/firebase.ts` | **baru** | Inisialisasi Firebase client (opsional) |
| `frontend/src/components/AuthProvider.tsx` | **baru** | Context auth global + jembatan token |
| `frontend/src/components/AuthButton.tsx` | **baru** | Tombol Masuk/Keluar di header |
| `frontend/src/lib/api.ts` | diubah | Interceptor melampirkan Bearer token |
| `frontend/src/app/layout.tsx` | diubah | Bungkus `AuthProvider` + pasang `AuthButton` |
| `frontend/src/app/verifikasi/page.tsx` | diubah | Banner ajakan login + handle 429/401 |
| `frontend/.env.local` | diubah | Tambah variabel `NEXT_PUBLIC_FIREBASE_*` |
| `frontend/package.json` | diubah | Tambah dependency `firebase` |

---

## 11. Catatan untuk Belajar & Pengembangan Lanjutan

### Konsep penting yang dipakai
- **Stateless auth dengan JWT:** server tidak menyimpan sesi; cukup memverifikasi tanda tangan token tiap request. Skalabel dan cocok untuk arsitektur serverless seperti Cloud Run.
- **Defense in depth:** UI (sembunyikan tombol) + API (verifikasi token & rate limit). Keamanan tidak pernah hanya di frontend.
- **Graceful degradation:** fitur opsional. Tanpa konfigurasi, aplikasi tetap berfungsi (mode anonim) alih-alih error.
- **Loose coupling:** layer API tidak bergantung langsung ke Firebase (lewat `setTokenProvider`).

### Keterbatasan saat ini & ide lanjutan
1. **Rate limiter in-memory** → tidak akurat untuk multi-instance. Lanjutan: pindah ke Firestore/Redis.
2. **History analisis belum ada** → token user sudah sampai backend, tinggal tambah penyimpanan (Firestore) untuk menyimpan riwayat per UID. Ini ada di roadmap tech stack.
3. **Belum ada halaman profil** → bisa menampilkan riwayat, kuota tersisa, dll.
4. **Refresh token** → Firebase SDK menangani perpanjangan token otomatis di klien; `getIdToken()` selalu mengembalikan token segar.

### Pertanyaan reflektif (untuk menguji pemahaman)
- Mengapa menyembunyikan tombol login di UI tidak cukup untuk mengamankan endpoint?
- Apa yang terjadi jika `FIREBASE_PROJECT_ID` di backend berbeda dengan `projectId` di frontend?
- Mengapa rate limiter in-memory bisa "bocor" saat aplikasi berjalan di banyak instance?

---

*Dokumen ini dibuat sebagai catatan sesi pengembangan fitur login aplikasi Faktain.*
