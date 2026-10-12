import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Panduan Cek Fakta — FAKTANYA",
  description:
    "Teknik praktis mengenali hoaks dan misinformasi sebelum mempercayai atau membagikannya.",
};

const STEPS = [
  {
    label: "Periksa Sumber",
    en: "Source",
    body: "Lihat siapa yang menerbitkan. Media kredibel mencantumkan nama redaksi, alamat, dan rekam jejak. Waspadai domain aneh yang meniru media besar.",
  },
  {
    label: "Baca Lebih dari Judul",
    en: "Context",
    body: "Judul sensasional sering tidak mewakili isi. Baca seluruh artikel sebelum menilai, karena hoaks bermain pada reaksi emosional yang cepat.",
  },
  {
    label: "Cek Tanggal",
    en: "Timing",
    body: "Berita lama kerap didaur ulang seolah baru terjadi. Pastikan konteks waktu peristiwa sesuai dengan klaim yang beredar.",
  },
  {
    label: "Telusuri Bukti",
    en: "Evidence",
    body: "Cari klaim yang sama di media arus utama. Jika hanya satu sumber tak dikenal yang memberitakan, kredibilitasnya patut diragukan.",
  },
  {
    label: "Kenali Timpa Teks",
    en: "Visual",
    body: "Tulisan pada screenshot berita, unggahan, atau kutipan bisa diganti sambil mempertahankan tampilannya. Cari judul atau kutipan di sumber asli, lalu bandingkan teksnya. Logo media bukan bukti keaslian. Timpa teks bisa berupa satire; sumber yang belum ditemukan bukan bukti bahwa gambar diedit.",
  },
  {
    label: "Kenali Bias Diri",
    en: "Bias",
    body: "Kita cenderung percaya informasi yang sesuai keyakinan. Justru pada saat itulah verifikasi paling dibutuhkan.",
  },
];

const RED_FLAGS = [
  "Mendesak Anda untuk segera membagikan ke banyak orang.",
  "Menggunakan huruf kapital berlebihan dan banyak tanda seru.",
  "Tidak mencantumkan sumber, tanggal, atau nama penulis.",
  "Mengklaim 'media tidak berani memberitakan ini'.",
  "Memuat kutipan tokoh tanpa tautan ke pernyataan aslinya.",
];

export default function PanduanPage() {
  return (
    <div>
      {/* Header */}
      <div className="rule-bottom pb-4 mb-8">
        <p className="kicker mb-2">Edukasi Publik</p>
        <h2
          className="lead-headline text-4xl md:text-5xl mb-3"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Panduan Cek Fakta
        </h2>
        <p className="text-[16px] text-[var(--color-meta)] leading-relaxed max-w-2xl">
          Enam langkah sederhana untuk menilai sebuah informasi sebelum Anda
          mempercayai, apalagi membagikannya.
        </p>
      </div>

      <section className="rule-top pt-6 mb-8" aria-labelledby="panduan-timpa-teks">
        <h3 id="panduan-timpa-teks" className="headline text-2xl mb-3">Periksa Tulisan dan Konteksnya</h3>
        <p className="text-[15px] leading-relaxed max-w-2xl mb-4">
          Klaim yang keliru dan screenshot yang disunting merupakan dua hal
          berbeda. FAKTANYA membaca teks pada gambar dan menelusuri bukti
          pembanding. Jika bukti belum cukup, keaslian tulisan belum dapat
          dipastikan. Untuk foto yang diduga berasal dari peristiwa lain,
          pencarian gambar terbalik dapat membantu penelusuran manual.
        </p>
        <Link href="/verifikasi?mode=timpa-teks" className="pill inline-block no-underline">
          Verifikasi Timpa Teks
        </Link>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-0">
        {/* Steps — Semafor-style structured rows */}
        <div className="md:pr-8 md:rule-right">
          {STEPS.map((step, i) => (
            <div key={step.label} className="semaform-row">
              <div className="semaform-label">
                {String(i + 1).padStart(2, "0")} · {step.label}
                <span>{step.en}</span>
              </div>
              <p className="text-[15px] leading-relaxed">{step.body}</p>
            </div>
          ))}
        </div>

        {/* Red flags sidebar */}
        <aside className="md:pl-8 mt-8 md:mt-0">
          <div className="rule-bottom pb-2 mb-4">
            <h3 className="section-label">Tanda Bahaya</h3>
          </div>
          <ul className="space-y-3">
            {RED_FLAGS.map((flag) => (
              <li key={flag} className="rule-bottom pb-3 flex gap-3">
                <span
                  className="shrink-0 font-bold"
                  style={{ color: "var(--color-accent-red)" }}
                >
                  !
                </span>
                <p className="text-[14px] text-[var(--color-meta)] leading-relaxed">
                  {flag}
                </p>
              </li>
            ))}
          </ul>

          <div
            className="mt-6 p-4"
            style={{ backgroundColor: "var(--color-highlight)" }}
          >
            <p className="section-label mb-2">Ragu?</p>
            <p className="text-[13px] text-[var(--color-meta)] leading-relaxed mb-3">
              Serahkan ke mesin. Tempel berita yang mencurigakan dan biarkan AI
              menelusuri sumbernya.
            </p>
            <Link href="/verifikasi" className="pill inline-block no-underline">
              Verifikasi Sekarang →
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
