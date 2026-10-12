"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SECTIONS = [
  { href: "/", label: "Beranda" },
  { href: "/news", label: "Berita Terkini" },
  { href: "/verifikasi", label: "Verifikasi" },
  { href: "/panduan", label: "Panduan Cek Fakta" },
  { href: "/tentang", label: "Tentang" },
];

export default function SiteNav() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <nav className="nav-bar rule-double" aria-label="Navigasi utama">
      {SECTIONS.map((section) => (
        <Link
          key={section.href}
          href={section.href}
          className={`nav-link ${isActive(section.href) ? "nav-link--active" : ""}`}
          aria-current={isActive(section.href) ? "page" : undefined}
        >
          {section.label}
        </Link>
      ))}
    </nav>
  );
}
