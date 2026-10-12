import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tentang — FAKTANYA",
  description:
    "Mengenal FAKTANYA, platform verifikasi berita Indonesia berbasis kecerdasan buatan.",
};

const FAQ = [
  {
    q: "Apa itu verifikasi timpa teks?",
    a: "Timpa teks mengganti tulisan pada gambar sambil mempertahankan tampilan berita, unggahan, atau kutipan aslinya. FAKTANYA membaca teks tersebut, memeriksa klaim, dan menelusuri sumber pembanding. Klaim yang salah belum membuktikan teks diedit; sumber yang belum ditemukan juga bukan bukti penyuntingan. Sistem belum memberikan kepastian forensik keaslian screenshot.",
  },
  {
    q: "Apakah timpa teks selalu hoaks?",
    a: "Tidak. Timpa teks bisa digunakan untuk lelucon, parodi, atau satire. Masalah muncul ketika konteks itu hilang dan hasilnya dianggap informasi asli. Niat satire tidak dapat disimpulkan hanya karena tulisannya terdengar aneh.",
  },
  {
    q: "Apakah hasil verifikasi selalu akurat?",
    a: "Tidak ada sistem yang sempurna. FAKTANYA memberi penilaian berbasis bukti yang ditemukan AI, namun keputusan akhir tetap di tangan Anda. Selalu rujuk silang dengan beberapa sumber tepercaya.",
  },
  {
    q: "Dari mana sumber beritanya?",
    a: "Berita terkini diambil dari Google News Indonesia. Untuk verifikasi, AI menelusuri media arus utama dan lembaga cek fakta secara langsung melalui pencarian web, lalu menjadikan temuannya sebagai bukti analisis (pendekatan RAG berbasis pencarian).",
  },
  {
    q: "Apakah layanan ini gratis?",
    a: "Ya. FAKTANYA dibangun sebagai alat bantu literasi digital untuk publik Indonesia.",
  },
  {
    q: "Apakah data saya disimpan?",
    a: "Teks dan gambar dikirim ke layanan AI untuk analisis. Aplikasi tidak menyimpan unggahan atau riwayat analisis. Kebijakan penyimpanan penyedia AI berlaku untuk pemrosesan eksternal.",
  },
];

export default function TentangPage() {
  return (
    <div>
      {/* Header */}
      <div className="rule-bottom pb-4 mb-8">
        <p className="kicker mb-2">Profil</p>
        <h2
          className="lead-headline text-4xl md:text-5xl"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Tentang FAKTANYA
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-0">
        {/* Editorial copy */}
        <div className="md:pr-8 md:rule-right">
          <p className="text-[17px] leading-relaxed justify-text drop-cap mb-4">
            FAKTANYA lahir dari satu keprihatinan sederhana: misinformasi
            menyebar lebih cepat daripada kebenaran. Setiap hari, kabar bohong
            berpindah dari satu layar ke layar lain, kerap tanpa sempat
            dipertanyakan. Kami percaya teknologi bisa membantu membalik
            keadaan itu.
          </p>
          <p className="text-[16px] leading-relaxed justify-text mb-6">
            Dengan memadukan model kecerdasan buatan dan penelusuran web secara
            langsung, FAKTANYA membandingkan klaim sebuah berita dengan sumber
            tepercaya, lalu menyajikannya dalam format yang jernih dan mudah
            dipahami. Tujuannya bukan menggantikan nalar Anda, melainkan
            mempersenjatainya.
          </p>

          <p className="text-[16px] leading-relaxed mb-6">
            Selain Cek Berita, FAKTANYA menonjolkan Verifikasi Timpa Teks untuk
            screenshot berita, unggahan, dan kutipan. Tampilan yang meyakinkan
            belum membuktikan bahwa sumber aslinya benar menulis demikian.
            Kami membantu menelusuri klaim, bukti pembanding, dan konteksnya.
          </p>

          <div className="rule-top pt-6 mb-6">
            <h3
              className="headline text-2xl mb-4"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              Cara Kerja
            </h3>
            <p className="text-[16px] leading-relaxed justify-text mb-4">
              FAKTANYA tidak mengandalkan ingatan model AI semata. Sebelum
              menilai, sistem menelusuri internet terlebih dahulu untuk
              mengumpulkan fakta terbaru, lalu menyuntikkan temuan itu sebagai
              bukti ke dalam analisis. Pendekatan ini dikenal sebagai{" "}
              <em>retrieval-augmented generation</em> (RAG) berbasis pencarian
              web, sehingga setiap penilaian berpijak pada data nyata, bukan
              sekadar tebakan model.
            </p>
            <ol className="space-y-4">
              <li className="flex gap-3">
                <span
                  className="shrink-0 font-bold"
                  style={{ fontFamily: "'Playfair Display', serif", color: "var(--color-accent-red)" }}
                >
                  1
                </span>
                <div>
                  <p className="headline text-lg mb-1" style={{ fontFamily: "'Playfair Display', serif" }}>
                    Penelusuran Bukti
                  </p>
                  <p className="text-[15px] text-[var(--color-meta)] leading-relaxed">
                    Klaim diubah menjadi kueri pencarian. Sistem menelusuri
                    media arus utama dan lembaga cek fakta Indonesia secara
                    langsung, lalu mengumpulkan sumber beserta tautannya.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <span
                  className="shrink-0 font-bold"
                  style={{ fontFamily: "'Playfair Display', serif", color: "var(--color-accent-red)" }}
                >
                  2
                </span>
                <div>
                  <p className="headline text-lg mb-1" style={{ fontFamily: "'Playfair Display', serif" }}>
                    Analisis Berdasar Fakta
                  </p>
                  <p className="text-[15px] text-[var(--color-meta)] leading-relaxed">
                    Temuan dari langkah pertama dijadikan landasan. Model
                    memecah klaim menjadi bagian-bagian spesifik—angka,
                    atribusi, waktu, konteks—dan memverifikasi tiap bagian
                    terhadap bukti yang ditemukan.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <span
                  className="shrink-0 font-bold"
                  style={{ fontFamily: "'Playfair Display', serif", color: "var(--color-accent-red)" }}
                >
                  3
                </span>
                <div>
                  <p className="headline text-lg mb-1" style={{ fontFamily: "'Playfair Display', serif" }}>
                    Putusan & Sumber
                  </p>
                  <p className="text-[15px] text-[var(--color-meta)] leading-relaxed">
                    Hasilnya berupa verdict per klaim, evidence, batasan, indikator,
                    dan tautan sumber yang dapat Anda telusuri sendiri untuk
                    memeriksa ulang.
                  </p>
                </div>
              </li>
            </ol>
          </div>

          <div className="rule-top pt-6">
            <h3
              className="headline text-2xl mb-4"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              Pertanyaan Umum
            </h3>
            <dl>
              {FAQ.map((item) => (
                <div key={item.q} className="rule-bottom py-4">
                  <dt
                    className="headline text-lg mb-1"
                    style={{ fontFamily: "'Playfair Display', serif" }}
                  >
                    {item.q}
                  </dt>
                  <dd className="text-[15px] text-[var(--color-meta)] leading-relaxed">
                    {item.a}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        {/* Tech sidebar */}
        <aside className="md:pl-8 mt-8 md:mt-0">
          <div className="rule-bottom pb-2 mb-4">
            <h3 className="section-label">Teknologi</h3>
          </div>
          <ul className="space-y-3 text-[14px]">
            <li className="rule-bottom pb-3">
              <p className="meta-text" style={{ color: "var(--color-ink)" }}>
                Model AI (LLM)
              </p>
              <p className="text-[var(--color-meta)]">
                Analisis bahasa & penalaran
              </p>
            </li>
            <li className="rule-bottom pb-3">
              <p className="meta-text" style={{ color: "var(--color-ink)" }}>
                Pencarian Web (RAG)
              </p>
              <p className="text-[var(--color-meta)]">
                Penelusuran sumber real-time
              </p>
            </li>
            <li className="rule-bottom pb-3">
              <p className="meta-text" style={{ color: "var(--color-ink)" }}>
                Next.js & FastAPI
              </p>
              <p className="text-[var(--color-meta)]">Antarmuka & layanan</p>
            </li>
          </ul>

          <div
            className="mt-6 p-4"
            style={{ backgroundColor: "var(--color-highlight)" }}
          >
            <p className="section-label mb-2">Mulai</p>
            <p className="text-[13px] text-[var(--color-meta)] leading-relaxed mb-3">
              Punya berita yang ingin dipastikan kebenarannya?
            </p>
            <Link href="/verifikasi" className="pill inline-block no-underline">
              Verifikasi Berita →
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
