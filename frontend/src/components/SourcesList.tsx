"use client";

import { Source, VerifiedClaim } from "@/types";

interface SourcesListProps {
  sources: Source[];
  claims: VerifiedClaim[];
}

export default function SourcesList({ sources, claims }: SourcesListProps) {
  const getClaimStatusStyle = (status: string) => {
    switch (status) {
      case "TERKONFIRMASI":
        return { color: "var(--color-accent-green)", label: "✓ TERKONFIRMASI" };
      case "DIBANTAH":
        return { color: "var(--color-accent-red)", label: "✗ DIBANTAH" };
      default:
        return { color: "var(--color-accent-yellow)", label: "? BELUM TERVERIFIKASI" };
    }
  };

  const getCredibilityStyle = (credibility: string) => {
    switch (credibility) {
      case "TERPERCAYA":
        return "var(--color-accent-green)";
      case "MERAGUKAN":
        return "var(--color-accent-red)";
      default:
        return "var(--color-meta)";
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Verified Claims */}
      {claims && claims.length > 0 && (
        <div>
          <h3
            className="headline text-xl mb-3 rule-bottom pb-2"
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Verifikasi Klaim
          </h3>
          <div className="space-y-3">
            {claims.map((claim, index) => {
              const style = getClaimStatusStyle(claim.status);
              return (
                <div key={index} className="rule-bottom pb-3">
                  <p className="text-[14px] font-bold mb-1">
                    &ldquo;{claim.claim}&rdquo;
                  </p>
                  <span
                    className="meta-text"
                    style={{ color: style.color, fontSize: "10px" }}
                  >
                    {style.label}
                  </span>
                  <p className="text-[13px] text-[var(--color-meta)] mt-1">
                    {claim.explanation}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Sources Found */}
      {sources && sources.length > 0 && (
        <div className="md:rule-left md:pl-6">
          <h3
            className="headline text-xl mb-3 rule-bottom pb-2"
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            Sumber Ditemukan
          </h3>
          <div className="space-y-2">
            {sources.map((source, index) => (
              <div key={index} className="rule-bottom pb-2">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[14px] text-[var(--color-ink)] underline hover:no-underline"
                >
                  {source.title}
                </a>
                <span
                  className="meta-text ml-2"
                  style={{
                    color: getCredibilityStyle(source.credibility),
                    fontSize: "10px",
                  }}
                >
                  {source.credibility}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
