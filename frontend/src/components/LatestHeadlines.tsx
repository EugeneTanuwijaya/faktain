"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getNewsFeed } from "@/lib/api";
import { NewsItem } from "@/types";

export default function LatestHeadlines() {
  const [articles, setArticles] = useState<NewsItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getNewsFeed(3)
      .then((data) => {
        if (active) setArticles(data.articles);
      })
      .catch(() => {
        if (active) setFailed(true);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="rule-bottom pb-3">
            <div className="skeleton h-4 w-full rounded-none mb-2" />
            <div className="skeleton h-3 w-1/3 rounded-none" />
          </div>
        ))}
      </div>
    );
  }

  if (failed || articles.length === 0) {
    return (
      <p className="text-[13px] text-[var(--color-meta)] leading-relaxed">
        Berita terkini belum tersedia. Pastikan backend berjalan, lalu kunjungi{" "}
        <Link href="/news" className="underline">
          halaman Berita Terkini
        </Link>
        .
      </p>
    );
  }

  const [lead, ...rest] = articles;

  return (
    <div>
      {/* Lead headline */}
      <a
        href={lead.link}
        target="_blank"
        rel="noopener noreferrer"
        className="no-underline group"
      >
        <p className="kicker mb-1">Sorotan</p>
        <h3
          className="lead-headline text-2xl md:text-3xl mb-2 group-hover:underline"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          {lead.title}
        </h3>
        <p className="meta-text" style={{ fontSize: "10px" }}>
          {lead.source}
          {lead.published ? ` · ${lead.published}` : ""}
        </p>
      </a>

      <div className="rule-bottom my-4" />

      {/* Secondary headlines */}
      <ul className="space-y-3">
        {rest.map((article) => (
          <li key={article.id} className="rule-bottom pb-3">
            <a
              href={article.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[15px] leading-snug no-underline hover:underline"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              {article.title}
            </a>
            <p className="meta-text mt-1" style={{ fontSize: "9px" }}>
              {article.source}
            </p>
          </li>
        ))}
      </ul>

      <Link
        href="/news"
        className="pill inline-block mt-4 no-underline"
      >
        Semua Berita →
      </Link>
    </div>
  );
}
