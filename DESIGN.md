# Newspaper UI/UX Design Guidelines (DESIGN.md)

File ini dirancang khusus untuk dibaca oleh AI Assistant atau untuk digunakan sebagai panduan arsitektur antarmuka (UI/UX) saat membangun website dengan gaya *editorial* atau koran cetak klasik. 

## 1. Filosofi Inti
Desain harus meniru tampilan klasik dan editorial dari koran cetak tradisional (*broadsheet*). Fokus utama ada pada hierarki tipografi yang kuat, arsitektur informasi yang padat, dan pembagian tata letak yang kaku menggunakan sistem *grid*. Desain harus minimalis, mengutamakan konten, dan menghindari ornamen visual yang tidak perlu.

## 2. Tata Letak & Sistem Grid (Layout)
- **Sistem CSS Grid:** Gunakan `display: grid;` dengan pembagian kolom multi-lajur (seperti 3 atau 4 kolom).
- **Tata Letak Asimetris:** Daripada membagi ruang sama rata, gunakan pembagian asimetris (misal: rasio `66% - 33%` atau pembagian 3 kolom di mana kolom tengah lebih lebar dari sisi kiri-kanan).
- **Garis Pembatas (Rules):** Gunakan garis vertikal dan horizontal yang tegas (`1px solid #111` atau `#d1d1d1`) di antara kolom atau artikel untuk meniru sekat di koran fisik.
- **Struktur Rapat:** Hindari ruang kosong (*whitespace*) yang terlalu besar antar artikel di halaman depan. Koran menempatkan informasi dengan padat.

## 3. Tipografi (Kunci Utama)
Tipografi adalah bintang utama dalam desain bergaya koran.
- **Headline & Judul Artikel (Serif):**
  - Font: `'Playfair Display', 'Merriweather', 'Times New Roman', serif;`
  - Aturan: Gunakan bobot tebal (Bold/Black), *line-height* yang rapat (`1.1` atau `1.2`), dan format *Sentence case*.
- **Teks Paragraf / Body (Serif):**
  - Font: `'Georgia', 'Times New Roman', serif;`
  - Aturan: *Line-height* nyaman (`1.5` atau `1.6`), ukuran font sekitar `15px` - `17px`, dengan perataan kiri atau rata kanan-kiri (*justify*).
- **Elemen UI / Navigasi / Meta Data (Sans-Serif):**
  - Font: `'Inter', 'Helvetica Neue', 'Arial', sans-serif;`
  - Aturan: Untuk label kategori, nama penulis (byline), tanggal, dan navigasi atas. Gunakan huruf kapital (UPPERCASE), ukuran kecil (`11px` - `13px`), dan *letter-spacing* yang longgar (`1px` - `2px`).
- **Drop Caps:** Paragraf pertama pada artikel utama harus menggunakan *drop cap* (huruf pertama berukuran besar mengambil 2-3 baris teks).

## 4. Palet Warna (Color Palette)
- **Background Utama (Kertas):** Hindari putih murni `#ffffff`. Gunakan warna putih pudar atau krem pucat untuk mengurangi ketegangan mata dan meniru kertas koran.
  - *Hex:* `#f4f4f0`, `#fdfcf8`, atau `#f9f7f1`
- **Teks Utama (Tinta):** Abu-abu sangat gelap atau hitam pudar. 
  - *Hex:* `#111111` atau `#1a1a1a`
- **Teks Sekunder (Meta):** Abu-abu netral untuk *caption* foto atau tanggal.
  - *Hex:* `#555555` atau `#767676`
- **Warna Aksen:** Sangat dibatasi. Jika dibutuhkan, gunakan merah gelap (seperti *breaking news*) atau *salmon pink* pucat (khas koran bisnis seperti Financial Times).

## 5. Komponen Khas Newspaper
- **Masthead:** Logo atau nama website di bagian paling atas halaman. Harus sangat besar, rata tengah, dan idealnya menggunakan font *Blackletter* (seperti Old English) atau font Serif yang sangat elegan.
- **Baris Tanggal & Edisi:** Garis horizontal ganda (atas dan bawah) persis di bawah Masthead yang berisi informasi hari, tanggal, lokasi, dan cuaca dalam font Sans-Serif kapital.
- **Gambar / Foto Jurnalistik:** Potongan foto dengan sudut siku-siku yang tegas (jangan gunakan *border-radius*). Selalu sertakan *caption* foto dan kredit (*credits*) dalam font Sans-Serif berukuran kecil persis di bawah foto.

## 6. Prompting AI (Vibe Coding Guide)
Jika kamu menggunakan AI (seperti Cursor, Bolt, atau agen coding lainnya) untuk men-generate kode, sertakan instruksi ini di awal prompt:
> *"Gunakan file DESIGN.md ini sebagai System UI/UX Guidelines. Jangan gunakan gaya SaaS atau desain modern dengan banyak shadow, gradient, atau border-radius. Gunakan gaya koran jadul, asimetris, dengan CSS Grid yang rapat dan garis pembatas tegas."*