"use client";

import { Indicator } from "@/types";

interface IndicatorListProps {
  indicators: Indicator[];
}

export default function IndicatorList({ indicators }: IndicatorListProps) {
  if (!indicators || indicators.length === 0) return null;

  const getSeverityLabel = (severity: string) => {
    switch (severity) {
      case "high":
        return { text: "TINGGI", color: "var(--color-accent-red)" };
      case "medium":
        return { text: "SEDANG", color: "var(--color-accent-yellow)" };
      case "low":
        return { text: "RENDAH", color: "var(--color-accent-green)" };
      default:
        return { text: severity.toUpperCase(), color: "var(--color-meta)" };
    }
  };

  return (
    <div className="mb-6">
      <h3
        className="headline text-xl mb-3 rule-bottom pb-2"
        style={{ fontFamily: "'Playfair Display', serif" }}
      >
        Indikator yang Ditemukan
      </h3>
      <div className="space-y-3">
        {indicators.map((indicator, index) => {
          const severity = getSeverityLabel(indicator.severity);
          return (
            <div
              key={index}
              className="flex gap-3 items-start rule-bottom pb-3"
            >
              <span
                className="meta-text shrink-0 px-2 py-0.5 border"
                style={{
                  color: severity.color,
                  borderColor: severity.color,
                  fontSize: "10px",
                }}
              >
                {severity.text}
              </span>
              <div>
                <p className="meta-text mb-0.5" style={{ color: "var(--color-ink)" }}>
                  {indicator.type}
                </p>
                <p className="text-[14px] text-[var(--color-meta)]">
                  {indicator.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
