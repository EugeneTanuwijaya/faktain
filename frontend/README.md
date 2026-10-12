# FAKTANYA - Frontend

Antarmuka Next.js untuk verifikasi teks, URL berita, dan screenshot.
Panduan lengkap ada di [README utama](../README.md).

Jalankan dari direktori ini:

```powershell
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm run dev
```

Isi `NEXT_PUBLIC_API_URL` dengan URL backend yang dapat diakses browser.
Konfigurasi Firebase opsional; tanpa konfigurasi, aplikasi memakai mode tamu.
Variabel `NEXT_PUBLIC_*` bersifat publik dan dimasukkan saat build.
Jangan isi dengan key backend, Langflow, atau provider AI.

```powershell
npm run lint
npm run typecheck
npm run test:e2e -- --workers=1
npm run build
```

Tes UI menggunakan respons API mock. Tes live hanya berjalan ketika
`FAKTAIN_LIVE_SMOKE=1` dan backend, Langflow, serta provider AI sudah dikonfigurasi.
