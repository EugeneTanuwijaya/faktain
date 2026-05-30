"use client";

import { useState } from "react";
import AnalysisForm from "@/components/AnalysisForm";
import VerdictCard from "@/components/VerdictCard";
import IndicatorList from "@/components/IndicatorList";
import SourcesList from "@/components/SourcesList";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { analyzeText, analyzeUrl } from "@/lib/api";
import { AnalysisResult } from "@/types";

export default function HomePage() {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (input: string, type: "text" | "url") => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const data =
        type === "url" ? await analyzeUrl(input) : await analyzeText(input);
      setResult(data);
    } catch (err: unknown) {
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(
          axiosErr.response?.data?.detail ||
            "Terjadi kesalahan saat menganalisis. Silakan coba lagi."
        );
      } else if (
        err &&
        typeof err === "object" &&
        "code" in err &&
        (err as { code?: string }).code === "ECONNABORTED"
      ) {
        setError(
          "Analisis memakan waktu terlalu lama (timeout). Server mungkin sedang " +
            "menunggu kuota AI atau memverifikasi sumber. Silakan coba lagi."
        );
      } else {
        setError("Tidak dapat terhubung ke server. Pastikan backend berjalan.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-0">
      {/* Main Column */}
      <div className="md:pr-6 md:rule-right">
        <AnalysisForm onSubmit={handleSubmit} isLoading={isLoading} />

        {isLoading && <LoadingSkeleton />}

        {error && (
          <div className="rule-top rule-bottom py-4 mb-6">
            <p className="meta-text mb-1" style={{ color: "var(--color-accent-red)" }}>
              KESALAHAN
            </p>
            <p className="text-[14px]">{error}</p>
          </div>
        )}

        {result && (
          <>
            <VerdictCard result={result} />
            <IndicatorList indicators={result.indicators} />
            <SourcesList
              sources={result.sources_found}
              claims={result.verified_claims}
            />
          </>
        )}
      </div>

      {/* Sidebar */}
      <aside className="md:pl-6 mt-8 md:mt-0">
        <div className="rule-bottom pb-3 mb-4">
          <h2
            className="headline text-xl"
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Cara Kerja
          </h2>
        </div>
        <div className="space-y-4 text-[14px] text-[var(--color-meta)]">
          <div className="rule-bottom pb-3">
            <p className="meta-text mb-1" style={{ color: "var(--color-ink)" }}>
              1. MASUKKAN BERITA
            </p>
            <p>Tempel teks berita atau URL artikel yang ingin diverifikasi.</p>
          </div>
          <div className="rule-bottom pb-3">
            <p className="meta-text mb-1" style={{ color: "var(--color-ink)" }}>
              2. ANALISIS AI
            </p>
            <p>
              Gemini AI menganalisis pola hoaks dan mencari sumber verifikasi di
              internet.
            </p>
          </div>
          <div className="rule-bottom pb-3">
            <p className="meta-text mb-1" style={{ color: "var(--color-ink)" }}>
              3. HASIL VERIFIKASI
            </p>
            <p>
              Dapatkan skor kepercayaan, indikator mencurigakan, dan sumber
              referensi.
            </p>
          </div>
        </div>

        <div className="mt-6 rule-top pt-4">
          <h3
            className="headline text-lg mb-2"
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Tentang
          </h3>
          <p className="text-[13px] text-[var(--color-meta)] leading-relaxed">
            Anti-Hoax menggunakan teknologi Gemini AI dengan Google Search
            Grounding untuk memverifikasi berita secara real-time. Sistem
            membandingkan klaim dengan sumber terpercaya Indonesia seperti
            Kompas, Tempo, dan Turnbackhoax.id.
          </p>
        </div>
      </aside>
    </div>
  );
}
