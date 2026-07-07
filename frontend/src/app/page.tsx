import Link from "next/link";
import LatestHeadlines from "@/components/LatestHeadlines";

export default function HomePage() {
  return (
    <div>
      {/* ---------------------------------------------------------------- */}
      {/* Front page: lead story + headlines rail                          */}
      {/* ---------------------------------------------------------------- */}
      <section className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-0">
        {/* Lead editorial block */}
        <div className="md:pr-8 md:rule-right">
          <p className="kicker mb-3">Laporan Utama</p>
          <h2
            className="lead-headline text-4xl md:text-6xl mb-4"
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Pisahkan Fakta dari Hoaks, dalam Hitungan Detik
          </h2>
          <p className="text-[17px] leading-relaxed justify-text drop-cap mb-4">
            Di tengah derasnya arus informasi, tak semua yang viral itu benar.
            Faktain menggunakan kecerdasan buatan untuk menelusuri sumber
            tepercaya, membandingkan klaim, dan memberi Anda penilaian yang
            jernih atas sebuah berita. Tempel teks atau tautan, dan biarkan
            mesin verifikasi bekerja.
          </p>
          <div className="flex flex-wrap gap-3 items-center">
            <Link href="/verifikasi" className="pill no-underline">
              Mulai Verifikasi →
            </Link>
            <Link href="/panduan" className="pill no-underline">
              Pelajari Cara Cek Fakta
            </Link>
          </div>

          {/* Stat strip */}
          <div className="grid grid-cols-3 gap-0 mt-8 rule-top rule-bottom">
            <div className="py-4 pr-4 rule-right">
              <p
                className="headline text-3xl"
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                3
              </p>
              <p className="meta-text mt-1" style={{ fontSize: "9px" }}>
                Tingkat Vonis
              </p>
            </div>
            <div className="py-4 px-4 rule-right">
              <p
                className="headline text-3xl"
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                100
              </p>
              <p className="meta-text mt-1" style={{ fontSize: "9px" }}>
                Skala Kredibilitas
              </p>
            </div>
            <div className="py-4 pl-4">
              <p
                className="headline text-3xl"
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                Live
              </p>
              <p className="meta-text mt-1" style={{ fontSize: "9px" }}>
                Penelusuran Sumber
              </p>
            </div>
          </div>
        </div>

        {/* Headlines rail */}
        <aside className="md:pl-8 mt-8 md:mt-0">
          <div className="rule-bottom pb-2 mb-4">
            <h3 className="section-label">Berita Terkini</h3>
          </div>
          <LatestHeadlines />
        </aside>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Semafor-style breakdown: "Apa yang kami nilai"                   */}
      {/* ---------------------------------------------------------------- */}
      <section className="mt-12 rule-top pt-8">
        <p className="kicker mb-2">Metodologi</p>
        <h2
          className="headline text-3xl md:text-4xl mb-6"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Bagaimana Kami Menilai Sebuah Berita
        </h2>

        <div className="semaform-row">
          <div className="semaform-label">
            Vonis
            <span>Verdict</span>
          </div>
          <p className="text-[15px] leading-relaxed">
            Setiap berita diberi label <strong>Kredibel</strong>,{" "}
            <strong>Perlu Dicek</strong>, atau{" "}
            <strong>Kemungkinan Hoaks</strong> — penilaian ringkas yang langsung
            bisa Anda pahami.
          </p>
        </div>
        <div className="semaform-row">
          <div className="semaform-label">
            Indikator
            <span>Signals</span>
          </div>
          <p className="text-[15px] leading-relaxed">
            Sistem menandai pola khas misinformasi: judul provokatif, klaim
            tanpa sumber, manipulasi emosi, hingga kutipan yang dipelintir.
          </p>
        </div>
        <div className="semaform-row">
          <div className="semaform-label">
            Sumber
            <span>Sources</span>
          </div>
          <p className="text-[15px] leading-relaxed">
            Klaim dibandingkan dengan media arus utama dan lembaga cek fakta
            seperti Kompas, Tempo, dan Turnbackhoax.id secara real-time.
          </p>
        </div>
        <div className="semaform-row">
          <div className="semaform-label">
            Saran
            <span>Takeaway</span>
          </div>
          <p className="text-[15px] leading-relaxed">
            Anda mendapat langkah lanjutan yang konkret — apa yang perlu
            dipastikan sebelum mempercayai atau membagikan berita tersebut.
          </p>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Section cards                                                    */}
      {/* ---------------------------------------------------------------- */}
      <section className="mt-12 rule-top pt-8">
        <h3 className="section-label mb-6">Jelajahi</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
          <Link
            href="/verifikasi"
            className="no-underline group md:pr-6 md:rule-right pb-6"
          >
            <p className="kicker mb-2">Alat</p>
            <h4
              className="headline text-2xl mb-2 group-hover:underline"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              Verifikasi Berita
            </h4>
            <p className="text-[14px] text-[var(--color-meta)] leading-relaxed">
              Tempel teks atau URL untuk mendapatkan skor kredibilitas dan
              analisis mendalam.
            </p>
          </Link>
          <Link
            href="/news"
            className="no-underline group md:px-6 md:rule-right pb-6"
          >
            <p className="kicker mb-2">Kurasi</p>
            <h4
              className="headline text-2xl mb-2 group-hover:underline"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              Berita Terkini
            </h4>
            <p className="text-[14px] text-[var(--color-meta)] leading-relaxed">
              Pantau berita terbaru Indonesia dan dapatkan ringkasan AI dalam
              satu klik.
            </p>
          </Link>
          <Link
            href="/panduan"
            className="no-underline group md:pl-6 pb-6"
          >
            <p className="kicker mb-2">Edukasi</p>
            <h4
              className="headline text-2xl mb-2 group-hover:underline"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              Panduan Cek Fakta
            </h4>
            <p className="text-[14px] text-[var(--color-meta)] leading-relaxed">
              Pelajari teknik praktis mengenali hoaks sebelum ikut
              menyebarkannya.
            </p>
          </Link>
        </div>
      </section>
    </div>
  );
}
