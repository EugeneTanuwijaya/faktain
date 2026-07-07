import type { Metadata } from "next";
import Link from "next/link";
import SiteNav from "@/components/SiteNav";
import { AuthProvider } from "@/components/AuthProvider";
import AuthButton from "@/components/AuthButton";
import "./globals.css";

export const metadata: Metadata = {
  title: "Faktain — Pendeteksi Hoaks Berbasis AI",
  description:
    "Verifikasi kredibilitas berita Indonesia secara real-time menggunakan kecerdasan buatan",
};

function getCurrentDate() {
  const options: Intl.DateTimeFormatOptions = {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  };
  return new Date().toLocaleDateString("id-ID", options);
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id">
      <body>
        <AuthProvider>
          <div className="top-frame" />
          <div className="max-w-[1200px] mx-auto px-4">
            {/* Top utility bar */}
            <div className="flex justify-between items-center py-2 rule-hair">
              <span className="meta-text" style={{ fontSize: "10px" }}>
                Edisi Digital
              </span>
              <span className="meta-text" style={{ fontSize: "10px" }}>
                {getCurrentDate()}
              </span>
              <AuthButton />
            </div>

          {/* Masthead */}
          <header className="text-center pt-6 pb-4">
            <Link href="/" className="no-underline">
              <h1
                className="headline text-6xl md:text-8xl tracking-tight"
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                FAKTAIN
              </h1>
            </Link>
            <p
              className="meta-text mt-2"
              style={{ fontSize: "12px", letterSpacing: "4px" }}
            >
              Jurnalisme Verifikasi &middot; Didukung Kecerdasan Buatan
            </p>
          </header>

          {/* Section navigation */}
          <SiteNav />

          {/* Main content */}
          <main className="mt-6">{children}</main>

          {/* Footer */}
          <footer className="rule-top mt-16 pt-8 pb-10">
            <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr_1fr] gap-8">
              <div>
                <h2
                  className="headline text-3xl mb-2"
                  style={{ fontFamily: "'Playfair Display', serif" }}
                >
                  FAKTAIN
                </h2>
                <p className="text-[14px] text-[var(--color-meta)] leading-relaxed max-w-md">
                  Platform verifikasi berita berbasis AI yang membantu publik
                  Indonesia membedakan fakta dari hoaks. Dibangun dengan Gemini
                  AI dan Google Search Grounding.
                </p>
              </div>
              <div>
                <p className="section-label mb-3">Bagian</p>
                <ul className="space-y-2">
                  <li>
                    <Link href="/news" className="text-[14px] no-underline hover:underline">
                      Berita Terkini
                    </Link>
                  </li>
                  <li>
                    <Link href="/verifikasi" className="text-[14px] no-underline hover:underline">
                      Verifikasi Berita
                    </Link>
                  </li>
                  <li>
                    <Link href="/panduan" className="text-[14px] no-underline hover:underline">
                      Panduan Cek Fakta
                    </Link>
                  </li>
                  <li>
                    <Link href="/tentang" className="text-[14px] no-underline hover:underline">
                      Tentang Kami
                    </Link>
                  </li>
                </ul>
              </div>
              <div>
                <p className="section-label mb-3">Sumber Tepercaya</p>
                <ul className="space-y-2 text-[14px] text-[var(--color-meta)]">
                  <li>Kompas</li>
                  <li>Tempo</li>
                  <li>Turnbackhoax.id</li>
                  <li>Google News Indonesia</li>
                </ul>
              </div>
            </div>
            <div className="rule-hair mt-8 pt-4 text-center">
              <p className="meta-text" style={{ fontSize: "10px" }}>
                &copy; 2026 Faktain &middot; Verifikasi Fakta untuk Indonesia
              </p>
            </div>
          </footer>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
