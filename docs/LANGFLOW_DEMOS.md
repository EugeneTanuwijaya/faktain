# Skenario demo Langflow Faktain

Jalankan backend/frontend, konfigurasi tiga flow dan provider 9Router mengikuti
[LANGFLOW.md](LANGFLOW.md). DuckDuckGo tidak memerlukan key pencarian. Rekam input, status
HTTP, `orchestration`, verdict, limitations dan URL/kutipan sumber yang dapat
pengamat buka. Jangan merekam key, gambar base64 atau payload pribadi dalam log.

Tes mock di repository digunakan untuk batas dan perilaku deterministik. Demo
live membuktikan integrasi yang benar-benar dijalankan; hasil model dapat berubah
menurut sumber, waktu dan model, sehingga bukan ukuran akurasi pemeriksaan fakta.
Jangan mengganti mock dengan klaim bahwa layanan eksternal telah berhasil.

| Skenario | Input/aksi | Yang diperiksa |
| --- | --- | --- |
| Teks | Masukkan satu klaim faktual spesifik, misalnya tanggal proklamasi Indonesia | Flow teks mengekstrak klaim, menyusun query, menerima artikel backend dan menilai bukti; hasil 2.0 mencantumkan kutipan artikel |
| URL | Tempel URL artikel publik yang dapat diambil | Backend memeriksa URL/redirect dan mengambil artikel; flow teks menerima isinya; tidak ada fetch URL bebas oleh model |
| Gambar + caption | Unggah screenshot tulisan jelas, sertakan caption bila perlu | Flow gambar membaca tulisan dan mengamati visual tanpa verdict awal; OCR/visual terpisah; klaim mempertahankan angka/waktu/lokasi |
| Gambar tidak terbaca | Unggah gambar tanpa tulisan terbaca dan tanpa caption faktual | OCR tidak menebak; klaim kosong/keterbatasan eksplisit; konteks tidak otomatis verified |
| Gambar serupa | Pakai foto bertema serupa tetapi berbeda dari foto penerbit | Kesamaan subjek belum menghasilkan SAME_IMAGE; konteks memerlukan kecocokan dan kutipan relevan |
| Pencarian tambahan | Pakai klaim yang mencakup detail waktu/lokasi/angka yang belum tercakup oleh artikel awal | Assessment mengidentifikasi kekurangan dan maksimal satu query tambahan per klaim; maksimal dua putaran dan lima slot unduhan total |
| Bukti cukup | Gunakan fixture terkontrol dengan artikel lengkap di tes, lalu coba contoh live | Assessment cukup tidak memanggil putaran 1; hasil live tidak boleh dipaksakan mengikuti fixture |
| Bukti tetap kurang | Gunakan klaim yang sumber publiknya belum dapat ditemukan | Setelah batas pencarian, verdict INSUFFICIENT_EVIDENCE dan detail yang belum terjawab; ketiadaan bukti tidak dianggap klaim salah |
| Ringkasan berita | Buka /news, pilih berita dan Ringkas AI | Backend mengurai tautan Google News dan mengambil artikel asli; flow summary hanya meringkas isi artikel, tidak menghasilkan pemeriksaan fakta |
| Layanan gagal | Pada environment tes, simulasi timeout/service error | Kegagalan diungkapkan; fallback hanya jika klaim dan artikel sudah tersedia, anggaran/waktu cukup; OCR/ekstraksi tidak diganti fallback |
| Output invalid | Jalankan tes fixture dengan ID palsu/duplikat, kutipan karangan, JSON terpotong | Schema/provenance ditolak; response tidak menerima verdict tanpa bukti tervalidasi |
| Prompt injection | Tes teks/artikel fixture berisi instruksi untuk membuka URL, mengubah batas atau membocorkan key | Data tetap tidak mengubah URL callback, kemampuan model atau batas backend; tool bebas tidak tersedia |

Untuk pengujian flow manual, Chat Input menerima hanya session ID yang diterbitkan
backend dan masih aktif. Mengimpor flow atau memanggilnya dengan ID acak tidak
membuktikan perjalanan pengguna. Gunakan endpoint aplikasi untuk membuat session
normal, atau fixture internal yang terkontrol saat menguji kontrak callback.

Contoh teks melalui API lokal (tanpa secret):

```powershell
$demoBody = @{ text = "Indonesia memproklamasikan kemerdekaan pada 17 Agustus 1945." } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/analyze -Method Post -ContentType application/json -Body $demoBody
```

Pada UI, periksa satu perjalanan utuh: /verifikasi -> submit teks -> hasil atau
keterbatasan terbaca, lalu /news -> Ringkas AI. `orchestration: langflow` hanya
menandai jalur yang dipilih; verdict/keterbatasan dan bukti eksekusi menentukan
apakah workflow selesai. Tidak adanya error browser saja bukan bukti retrieval.

Hasil aktual pada 2026-10-11: tiga flow diimpor/dikonfigurasi; teks satu klaim
berjalan melalui Langflow (sekitar 5,2 detik); OCR gambar sintetis berhasil
(sekitar 8,8 detik); ringkasan artikel asli 629 karakter berhasil (sekitar 4,7
detik). Satu perjalanan browser live lulus (10,3 detik). Pada smoke terdahulu, search dimatikan hanya
pada environment proses smoke backend karena key Exa belum tersedia; hasil
verifikasi teks/konteks gambar tetap insufficient.

Untuk mengulang tes browser live setelah konfigurasi:

```powershell
cd frontend
$env:FAKTAIN_LIVE_SMOKE = "1"
npm run test:e2e -- langflow-live.spec.ts --workers=1
```

Backend harus berjalan di port 8000 dan mengizinkan origin port 3100 dari server
frontend tes melalui `FRONTEND_URL`. Konfigurasi CORS smoke tersebut bersifat
runtime; jangan memasukkan key atau endpoint internal ke frontend. Dengan pencarian DuckDuckGo aktif, jalankan demo dan skenario tambahan serta
kandidat gambar. Skenario ini belum diverifikasi live; fixture/mock hanya
membuktikan batas dan kontraknya. Lihat hasil lengkap, privasi dan blocker pada
[LANGFLOW.md](LANGFLOW.md).

Revisi pencarian 2026-10-11 memakai DuckDuckGo. Probe awal gagal karena DNS lokal.
Perbaikan POST dan `SEARCH_DNS_OVER_HTTPS=true` menghasilkan tiga URL, dua artikel
berhasil diambil, dan satu analisis teks Langflow `SUPPORTED` dengan dua kutipan
tervalidasi. Skenario tambahan/gambar tetap perlu diuji live. Lihat LANGFLOW.md.

Setelah perbaikan, satu tes perjalanan frontend live lulus (10,9 detik); CORS proses backend mengizinkan origin tes 3100. Tes tambahan/gambar belum diulang live.

Uji live lanjutan setelah JSON mode/prompt modalitas: screenshot tanpa caption
menghasilkan OCR tepat, 1 klaim SUPPORTED dan 2 kandidat DIFFERENT; konteks gambar
insufficient. Gambar kosong menghasilkan 0 klaim. Foto publik tetap insufficient,
sehingga kecocokan positif/konteks VERIFIED belum terbukti. Skenario tambahan
"dihadiri tepat 500 orang" mengeksekusi putaran 0/1 dengan 4 artikel; detail jumlah
belum terbukti dan verdict insufficient. 193 tes backend lulus. Detail kegagalan
awal, perbaikan dan cooldown 429/CAPTCHA tersedia pada bagian terbaru LANGFLOW.md.
