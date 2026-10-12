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
            Terlihat Asli. Apa Faktanya?
          </h2>
          <p className="text-[17px] leading-relaxed justify-text drop-cap mb-4">
            Tampilan berita dan logo media bisa ditiru. FAKTANYA membantu Anda
            memeriksa klaim berita dan menelusuri keaslian teks pada gambar.
            Tempel teks atau tautan, atau unggah screenshot yang Anda ragukan.
            Telusuri bukti dan konteksnya sebelum membagikan.
          </p>
          <div className="flex flex-wrap gap-3 items-center">
            <Link href="/verifikasi" className="pill no-underline">
              Cek Berita
            </Link>
            <Link href="/verifikasi?mode=timpa-teks" className="pill no-underline">
              Verifikasi Timpa Teks
            </Link>
          </div>

          {/* Stat strip */}
          <div className="grid grid-cols-3 gap-0 mt-8 rule-top rule-bottom">
            <div className="py-4 pr-4 rule-right">
              <p
                className="headline text-3xl"
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                5
              </p>
              <p className="meta-text mt-1" style={{ fontSize: "9px" }}>
                Verdict Berbasis Bukti
              </p>
            </div>
            <div className="py-4 px-4 rule-right">
              <p
                className="headline text-3xl"
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                3
              </p>
              <p className="meta-text mt-1" style={{ fontSize: "9px" }}>
                Jenis Input
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

      <section className="mt-10 rule-top rule-bottom py-6" aria-labelledby="timpa-teks-heading">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-6">
          <div>
            <h2 id="timpa-teks-heading" className="headline text-2xl md:text-3xl mb-3">
              Verifikasi Timpa Teks
            </h2>
            <p className="text-[15px] text-[var(--color-meta)]">
              Benarkah sumber aslinya menulis demikian?
            </p>
          </div>
          <div>
            <p className="text-[16px] leading-relaxed mb-3">
              Timpa teks mengganti tulisan pada screenshot berita, unggahan,
              atau kutipan sambil mempertahankan tampilannya. Hasilnya bisa
              berupa lelucon atau satire yang disangka informasi asli ketika
              konteksnya hilang.
            </p>
            <p className="text-[14px] text-[var(--color-meta)] leading-relaxed mb-4">
              Unggah screenshot untuk membaca teksnya, memeriksa klaim, dan
              menelusuri sumber pembanding. Timpa teks tidak otomatis berarti
              hoaks; sumber yang belum ditemukan juga bukan bukti penyuntingan.
            </p>
            <Link href="/verifikasi?mode=timpa-teks" className="pill inline-block no-underline">
              Unggah Screenshot
            </Link>
          </div>
        </div>
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
            Setiap klaim diberi verdict SUPPORTED, CONTRADICTED, MISLEADING,
            PARTIALLY_SUPPORTED, atau INSUFFICIENT_EVIDENCE sesuai bukti yang
            tersedia. Periksa evidence per klaim sebelum menyimpulkan.
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
            Indikator gaya bahasa merupakan petunjuk untuk diperiksa lebih lanjut.
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
              Cek Berita
            </h4>
            <p className="text-[14px] text-[var(--color-meta)] leading-relaxed">
              Tempel teks atau tautan artikel untuk memeriksa klaim, bukti,
              sumber, dan batasan hasil.
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
