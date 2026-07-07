"use client";

import { AnalysisResult } from "@/types";

interface VerdictCardProps {
  result: AnalysisResult;
}

export default function VerdictCard({ result }: VerdictCardProps) {
  const getBadgeClass = () => {
    switch (result.verdict) {
      case "KREDIBEL":
        return "badge-kredibel";
      case "PERLU DICEK":
        return "badge-perlu-dicek";
      case "KEMUNGKINAN HOAKS":
        return "badge-hoaks";
      default:
        return "";
    }
  };

  const getScoreColor = () => {
    if (result.confidence_score >= 75) return "var(--color-accent-green)";
    if (result.confidence_score >= 40) return "var(--color-accent-yellow)";
    return "var(--color-accent-red)";
  };

  return (
    <div className="rule-top rule-bottom py-6 mb-6">
      <p className="kicker mb-3">Hasil Verifikasi</p>

      {/* Verdict Header */}
      <div className="flex flex-col md:flex-row md:items-center gap-4 mb-2">
        <span
          className={`meta-text inline-block px-4 py-2 font-bold text-[13px] ${getBadgeClass()}`}
        >
          {result.verdict}
        </span>
        <div className="flex items-baseline gap-2">
          <span
            className="text-4xl font-bold"
            style={{
              fontFamily: "'Playfair Display', serif",
              color: getScoreColor(),
            }}
          >
            {result.confidence_score}
          </span>
          <span className="meta-text">/ 100 Skor Kredibilitas</span>
        </div>
      </div>

      {/* Score scale hint */}
      <p className="meta-text text-[11px] text-[var(--color-meta)] mb-2">
        Skala: 0 = kemungkinan hoaks &middot; 100 = kredibel
      </p>

      {/* Semafor-style breakdown */}
      <div className="mt-4">
        <div className="semaform-row">
          <div className="semaform-label">
            Analisis
            <span>Reasoning</span>
          </div>
          <p className="text-[15px] leading-relaxed">{result.reasoning}</p>
        </div>

        {result.suggestion && (
          <div className="semaform-row">
            <div className="semaform-label">
              Saran
              <span>Takeaway</span>
            </div>
            <p className="text-[15px] leading-relaxed italic text-[var(--color-meta)]">
              {result.suggestion}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
