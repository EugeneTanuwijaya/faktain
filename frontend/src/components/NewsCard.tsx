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
          className="headline text-xl mb-1 hover:underline cursor-pointer"
          style={{ fontFamily: "'Playfair Display', serif", lineHeight: "1.2" }}
        >
          {article.title}
        </h3>
      </a>
      <div className="flex items-center gap-2 mb-2">
        <span className="kicker" style={{ fontSize: "10px" }}>
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
        className="pill disabled:opacity-50"
      >
        {isAnalyzing ? "Meringkas..." : "Ringkas AI →"}
      </button>
    </article>
  );
}
