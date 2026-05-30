import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Anti-Hoax — Pendeteksi Hoaks Berbasis AI",
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
        <div className="max-w-[1200px] mx-auto px-4">
          {/* Masthead */}
          <header className="text-center py-6">
            <Link href="/" className="no-underline">
              <h1
                className="headline text-5xl md:text-7xl tracking-tight"
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                FAKTAIN
              </h1>
            </Link>
            <p
              className="meta-text mt-1"
              style={{ fontSize: "12px", letterSpacing: "3px" }}
            >
              Pendeteksi Hoaks Berbasis Kecerdasan Buatan
            </p>
          </header>

          {/* Date bar */}
          <div className="rule-double flex justify-between items-center mb-4">
            <span className="meta-text">{getCurrentDate()}</span>
            <nav className="flex gap-6">
              <Link
                href="/"
                className="meta-text no-underline hover:text-[var(--color-ink)] transition-colors"
              >
                Beranda
              </Link>
              <Link
                href="/news"
                className="meta-text no-underline hover:text-[var(--color-ink)] transition-colors"
              >
                Berita Terkini
              </Link>
            </nav>
            <span className="meta-text">Jakarta, Indonesia</span>
          </div>

          {/* Main content */}
          <main>{children}</main>

          {/* Footer */}
          <footer className="rule-top mt-12 py-6 text-center">
            <p className="meta-text">
              &copy; 2025 Anti-Hoax &middot; Didukung oleh Gemini AI &middot;
              Verifikasi fakta untuk Indonesia
            </p>
          </footer>
        </div>
      </body>
    </html>
  );
}
