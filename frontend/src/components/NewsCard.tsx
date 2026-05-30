"use client";

import { NewsItem } from "@/types";

interface NewsCardProps {
  article: NewsItem;
  onAnalyze: (id: string) => void;
  isAnalyzing: boolean;
}

export default function NewsCard({ article, onAnalyze, isAnalyzing }: NewsCardProps) {
  return (
    <article className="rule-bottom pb-4 mb-4">
      <a
        href={article.link}
        target="_blank"
        rel="noopener noreferrer"
        className="no-underline"
      >
        <h3
          className="headline text-lg mb-1 hover:underline cursor-pointer"
          style={{ fontFamily: "'Playfair Display', serif", lineHeight: "1.2" }}
        >
          {article.title}
        </h3>
      </a>
      <div className="flex items-center gap-2 mb-2">
        <span className="meta-text" style={{ fontSize: "10px" }}>
          {article.source}
        </span>
        {article.published && (
          <>
            <span className="text-[var(--color-rule-light)]">&middot;</span>
            <span className="meta-text" style={{ fontSize: "10px" }}>
              {article.published}
            </span>
          </>
        )}
      </div>
      {article.summary && (
        <p className="text-[14px] text-[var(--color-meta)] mb-2 leading-relaxed">
          {article.summary}
        </p>
      )}
      <button
        onClick={() => onAnalyze(article.id)}
        disabled={isAnalyzing}
        className="meta-text text-[10px] px-3 py-1 border border-[var(--color-rule-light)] bg-transparent cursor-pointer hover:bg-[var(--color-ink)] hover:text-white transition-colors disabled:opacity-50"
      >
        {isAnalyzing ? "MENGANALISIS..." : "CEK FAKTA →"}
      </button>
    </article>
  );
}
