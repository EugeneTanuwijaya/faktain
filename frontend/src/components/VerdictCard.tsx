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
      {/* Verdict Header */}
      <div className="flex flex-col md:flex-row md:items-center gap-4 mb-4">
        <span
          className={`meta-text inline-block px-4 py-2 font-bold text-[13px] ${getBadgeClass()}`}
        >
          {result.verdict}
        </span>
        <div className="flex items-center gap-3">
          <span className="meta-text">Skor Kepercayaan:</span>
          <span
            className="text-3xl font-bold"
            style={{
              fontFamily: "'Playfair Display', serif",
              color: getScoreColor(),
            }}
          >
            {result.confidence_score}
          </span>
          <span className="meta-text">/ 100</span>
        </div>
      </div>

      {/* Reasoning */}
      <div className="mb-4">
        <h3
          className="headline text-lg mb-2"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Kesimpulan Analisis
        </h3>
        <p className="text-[15px] leading-relaxed drop-cap">
          {result.reasoning}
        </p>
      </div>

      {/* Suggestion */}
      {result.suggestion && (
        <div className="rule-top pt-3 mt-3">
          <p className="meta-text mb-1">Saran:</p>
          <p className="text-[14px] italic text-[var(--color-meta)]">
            {result.suggestion}
          </p>
        </div>
      )}
    </div>
  );
}
