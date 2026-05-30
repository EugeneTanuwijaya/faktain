"use client";

import { useState, useEffect } from "react";
import NewsCard from "@/components/NewsCard";
import VerdictCard from "@/components/VerdictCard";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import IndicatorList from "@/components/IndicatorList";
import SourcesList from "@/components/SourcesList";
import { getNewsFeed, analyzeNewsArticle } from "@/lib/api";
import { NewsItem, AnalysisResult } from "@/types";

export default function NewsPage() {
  const [articles, setArticles] = useState<NewsItem[]>([]);
  const [isLoadingFeed, setIsLoadingFeed] = useState(true);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadNews();
  }, []);

  const loadNews = async () => {
    try {
      const data = await getNewsFeed(20);
      setArticles(data.articles);
    } catch {
      setError("Gagal memuat berita. Pastikan backend berjalan.");
    } finally {
      setIsLoadingFeed(false);
    }
  };

  const handleAnalyze = async (newsId: string) => {
    setAnalyzingId(newsId);
    setAnalysisResult(null);
    setError(null);

    try {
      const result = await analyzeNewsArticle(newsId);
      setAnalysisResult(result);
    } catch (err: unknown) {
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(
          axiosErr.response?.data?.detail || "Gagal menganalisis artikel."
        );
      } else {
        setError("Tidak dapat terhubung ke server.");
      }
    } finally {
      setAnalyzingId(null);
    }
  };

  return (
    <div>
      <div className="rule-bottom pb-3 mb-6">
        <h2
          className="headline text-3xl md:text-4xl"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Berita Terkini Indonesia
        </h2>
        <p className="meta-text mt-1">
          Sumber: Google News Indonesia &middot; Klik &ldquo;Cek Fakta&rdquo;
          untuk analisis AI
        </p>
      </div>

      {/* Analysis Result (if any) */}
      {analysisResult && (
        <div className="mb-8">
          <div className="rule-bottom pb-2 mb-4">
            <h3
              className="headline text-xl"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              Hasil Analisis
            </h3>
          </div>
          <VerdictCard result={analysisResult} />
          <IndicatorList indicators={analysisResult.indicators} />
          <SourcesList
            sources={analysisResult.sources_found}
            claims={analysisResult.verified_claims}
          />
        </div>
      )}

      {analyzingId && <LoadingSkeleton />}

      {error && (
        <div className="rule-top rule-bottom py-4 mb-6">
          <p className="meta-text mb-1" style={{ color: "var(--color-accent-red)" }}>
            KESALAHAN
          </p>
          <p className="text-[14px]">{error}</p>
        </div>
      )}

      {/* News Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
        {/* Main news column */}
        <div className="md:col-span-2 md:pr-6 md:rule-right">
          {isLoadingFeed ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="rule-bottom pb-4">
                  <div className="skeleton h-5 w-4/5 rounded-none mb-2" />
                  <div className="skeleton h-3 w-1/3 rounded-none mb-2" />
                  <div className="skeleton h-3 w-full rounded-none" />
                </div>
              ))}
            </div>
          ) : (
            articles.slice(0, 14).map((article) => (
              <NewsCard
                key={article.id}
                article={article}
                onAnalyze={handleAnalyze}
                isAnalyzing={analyzingId === article.id}
              />
            ))
          )}
        </div>

        {/* Side column */}
        <div className="md:pl-6 mt-6 md:mt-0">
          <div className="rule-bottom pb-2 mb-4">
            <h3
              className="meta-text"
              style={{ color: "var(--color-ink)", fontSize: "12px" }}
            >
              BERITA LAINNYA
            </h3>
          </div>
          {articles.slice(14).map((article) => (
            <div key={article.id} className="rule-bottom pb-3 mb-3">
              <a
                href={article.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[13px] leading-tight no-underline hover:underline"
                style={{ fontFamily: "'Playfair Display', serif" }}
              >
                {article.title}
              </a>
              <p className="meta-text mt-0.5" style={{ fontSize: "9px" }}>
                {article.source}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
