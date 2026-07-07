"use client";

import { useState, useEffect } from "react";
import CategoryTabs, { NEWS_CATEGORIES } from "@/components/CategoryTabs";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { getNewsFeed, summarizeNewsArticle } from "@/lib/api";
import { NewsItem, NewsSummary } from "@/types";

function timeAgo(published: string): string {
  if (!published) return "";
  const date = new Date(published);
  if (isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Baru saja";
  if (mins < 60) return `${mins} mnt lalu`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} jam lalu`;
  const days = Math.floor(hours / 24);
  return `${days} hari lalu`;
}

interface StoryProps {
  article: NewsItem;
  onAnalyze: (id: string) => void;
  isAnalyzing: boolean;
}

/** Large lead story (top-left hero). */
function LeadStory({ article, onAnalyze, isAnalyzing }: StoryProps) {
  return (
    <article>
      <a
        href={article.link}
        target="_blank"
        rel="noopener noreferrer"
        className="no-underline group"
      >
        <h3
          className="lead-headline text-3xl md:text-4xl mb-2 group-hover:underline"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          {article.title}
        </h3>
      </a>
      <div className="flex items-center gap-2 mb-3">
        <span className="kicker" style={{ fontSize: "10px" }}>
          {article.source || "Google News"}
        </span>
        {article.published && (
          <>
            <span className="text-[var(--color-rule-light)]">&middot;</span>
            <span className="meta-text" style={{ fontSize: "10px" }}>
              {timeAgo(article.published)}
            </span>
          </>
        )}
      </div>
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

/** Standard story block with headline + meta + analyze button. */
function Story({ article, onAnalyze, isAnalyzing }: StoryProps) {
  return (
    <article className="rule-bottom pb-4 mb-4">
      <a
        href={article.link}
        target="_blank"
        rel="noopener noreferrer"
        className="no-underline group"
      >
        <h3
          className="headline text-lg mb-1 group-hover:underline"
          style={{ fontFamily: "'Playfair Display', serif", lineHeight: "1.2" }}
        >
          {article.title}
        </h3>
      </a>
      <div className="flex items-center gap-2 mb-2">
        <span className="kicker" style={{ fontSize: "9px" }}>
          {article.source}
        </span>
        {article.published && (
          <span className="meta-text" style={{ fontSize: "9px" }}>
            {timeAgo(article.published)}
          </span>
        )}
      </div>
      <button
        onClick={() => onAnalyze(article.id)}
        disabled={isAnalyzing}
        className="pill disabled:opacity-50"
        style={{ fontSize: "9px", padding: "4px 10px" }}
      >
        {isAnalyzing ? "Meringkas..." : "Ringkas AI →"}
      </button>
    </article>
  );
}

/** Compact headline-only item for the rails. */
function HeadlineItem({ article }: { article: NewsItem }) {
  return (
    <div className="rule-bottom pb-3 mb-3">
      <a
        href={article.link}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[14px] leading-snug no-underline hover:underline"
        style={{ fontFamily: "'Playfair Display', serif" }}
      >
        {article.title}
      </a>
      <p className="meta-text mt-1" style={{ fontSize: "9px" }}>
        {article.source}
        {article.published ? ` · ${timeAgo(article.published)}` : ""}
      </p>
    </div>
  );
}

export default function NewsPage() {
  const [category, setCategory] = useState("terkini");
  const [articles, setArticles] = useState<NewsItem[]>([]);
  const [isLoadingFeed, setIsLoadingFeed] = useState(true);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [summary, setSummary] = useState<NewsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getNewsFeed(24, category)
      .then((data) => {
        if (active) setArticles(data.articles);
      })
      .catch(() => {
        if (active) setError("Gagal memuat berita. Pastikan backend berjalan.");
      })
      .finally(() => {
        if (active) setIsLoadingFeed(false);
      });
    return () => {
      active = false;
    };
  }, [category]);

  const handleCategoryChange = (key: string) => {
    if (key === category) return;
    setIsLoadingFeed(true);
    setError(null);
    setCategory(key);
  };

  const handleAnalyze = async (newsId: string) => {
    setAnalyzingId(newsId);
    setSummary(null);
    setError(null);
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    try {
      const result = await summarizeNewsArticle(newsId);
      setSummary(result);
    } catch (err: unknown) {
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || "Gagal meringkas artikel.");
      } else if (
        err &&
        typeof err === "object" &&
        "code" in err &&
        (err as { code?: string }).code === "ECONNABORTED"
      ) {
        setError(
          "Ringkasan memakan waktu terlalu lama (timeout). Silakan coba lagi."
        );
      } else {
        setError("Tidak dapat terhubung ke server.");
      }
    } finally {
      setAnalyzingId(null);
    }
  };

  const categoryLabel =
    NEWS_CATEGORIES.find((c) => c.key === category)?.label ?? "Terkini";

  // Distribute the feed across the front-page regions.
  const lead = articles[0];
  const leadSecondary = articles.slice(1, 3);
  const featured = articles[3];
  const featuredRail = articles.slice(4, 6); // Sorotan = featured + 2 = 3 total
  const mainStories = articles.slice(6, 14);
  const moreList = articles.slice(14, 24);

  return (
    <div>
      {/* Section header */}
      <div className="flex flex-wrap items-end justify-between gap-2 rule-bottom pb-3 mb-3">
        <div>
          <p className="kicker mb-1">Kurasi Harian</p>
          <h2
            className="lead-headline text-3xl md:text-4xl"
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Berita Terkini
          </h2>
        </div>
        <p className="meta-text" style={{ fontSize: "10px" }}>
          Google News Indonesia
        </p>
      </div>

      {/* Category tabs */}
      <CategoryTabs
        active={category}
        onChange={handleCategoryChange}
        disabled={isLoadingFeed}
      />

      {/* Summary result (if any) */}
      {summary && (
        <div className="mt-6 mb-6">
          <div className="rule-bottom pb-2 mb-4">
            <h3 className="section-label">Ringkasan AI</h3>
          </div>
          <article className="rule-top rule-bottom py-4">
            <h4
              className="headline text-xl mb-2"
              style={{ fontFamily: "'Playfair Display', serif", lineHeight: "1.2" }}
            >
              {summary.title}
            </h4>
            {summary.source && (
              <p className="kicker mb-3" style={{ fontSize: "10px" }}>
                {summary.source}
              </p>
            )}
            <p className="text-[15px] leading-relaxed mb-3 justify-text">
              {summary.summary}
            </p>
            <a
              href={summary.original_url}
              target="_blank"
              rel="noopener noreferrer"
              className="meta-text text-[10px] hover:underline"
              style={{ color: "var(--color-accent-red)" }}
            >
              BACA ARTIKEL ASLI →
            </a>
          </article>
        </div>
      )}

      {analyzingId && <LoadingSkeleton />}

      {error && (
        <div className="rule-top rule-bottom py-4 mt-6 mb-6">
          <p className="meta-text mb-1" style={{ color: "var(--color-accent-red)" }}>
            Kesalahan
          </p>
          <p className="text-[14px]">{error}</p>
        </div>
      )}

      {/* Front page */}
      {isLoadingFeed ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 mt-6">
          <div className="md:col-span-2 md:pr-6 md:rule-right space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="rule-bottom pb-4">
                <div className="skeleton h-6 w-4/5 rounded-none mb-2" />
                <div className="skeleton h-3 w-1/3 rounded-none" />
              </div>
            ))}
          </div>
          <div className="md:pl-6 mt-6 md:mt-0 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="rule-bottom pb-3">
                <div className="skeleton h-4 w-full rounded-none mb-2" />
                <div className="skeleton h-3 w-1/4 rounded-none" />
              </div>
            ))}
          </div>
        </div>
      ) : articles.length === 0 ? (
        <p className="text-[15px] text-[var(--color-meta)] mt-8">
          Tidak ada berita untuk kategori ini saat ini.
        </p>
      ) : (
        <>
          {/* Hero row */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-0 mt-6 pb-6 rule-bottom">
            {/* Lead + secondary (2 cols) */}
            <div className="md:col-span-2 md:pr-6 md:rule-right">
              {lead && (
                <LeadStory
                  article={lead}
                  onAnalyze={handleAnalyze}
                  isAnalyzing={analyzingId === lead.id}
                />
              )}
              {leadSecondary.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-0 mt-5 rule-top pt-5">
                  {leadSecondary.map((article, i) => (
                    <div
                      key={article.id}
                      className={i === 0 ? "sm:pr-5 sm:rule-right" : "sm:pl-5"}
                    >
                      <Story
                        article={article}
                        onAnalyze={handleAnalyze}
                        isAnalyzing={analyzingId === article.id}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Featured rail */}
            <aside className="md:pl-6 mt-8 md:mt-0">
              <h3 className="section-label mb-3">Sorotan</h3>
              {featured && (
                <article className="rule-bottom pb-4 mb-4">
                  <a
                    href={featured.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="no-underline group"
                  >
                    <h4
                      className="headline text-xl mb-1 group-hover:underline"
                      style={{
                        fontFamily: "'Playfair Display', serif",
                        lineHeight: "1.2",
                      }}
                    >
                      {featured.title}
                    </h4>
                  </a>
                  <p className="kicker" style={{ fontSize: "9px" }}>
                    {featured.source}
                    {featured.published ? ` · ${timeAgo(featured.published)}` : ""}
                  </p>
                </article>
              )}
              {featuredRail.map((article) => (
                <HeadlineItem key={article.id} article={article} />
              ))}
            </aside>
          </section>

          {/* Lower grid */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-0 mt-6">
            {/* Main story list (2 cols, split into two columns) */}
            <div className="md:col-span-2 md:pr-6 md:rule-right">
              <h3 className="section-label mb-4">{categoryLabel} Lainnya</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-0">
                <div className="sm:pr-5 sm:rule-right">
                  {mainStories
                    .filter((_, i) => i % 2 === 0)
                    .map((article) => (
                      <Story
                        key={article.id}
                        article={article}
                        onAnalyze={handleAnalyze}
                        isAnalyzing={analyzingId === article.id}
                      />
                    ))}
                </div>
                <div className="sm:pl-5">
                  {mainStories
                    .filter((_, i) => i % 2 === 1)
                    .map((article) => (
                      <Story
                        key={article.id}
                        article={article}
                        onAnalyze={handleAnalyze}
                        isAnalyzing={analyzingId === article.id}
                      />
                    ))}
                </div>
              </div>
            </div>

            {/* More headlines rail */}
            <aside className="md:pl-6 mt-8 md:mt-0">
              <h3 className="section-label mb-4">Berita Lainnya</h3>
              {moreList.map((article) => (
                <HeadlineItem key={article.id} article={article} />
              ))}
            </aside>
          </section>
        </>
      )}
    </div>
  );
}
