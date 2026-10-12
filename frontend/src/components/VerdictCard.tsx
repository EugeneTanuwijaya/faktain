"use client";

import { AnalysisResult, Verdict } from "@/types";

const LABELS: Record<Verdict, string> = {
  SUPPORTED: "Didukung bukti", CONTRADICTED: "Bertentangan dengan bukti", MISLEADING: "Konteks menyesatkan",
  PARTIALLY_SUPPORTED: "Sebagian didukung", INSUFFICIENT_EVIDENCE: "Bukti belum cukup",
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const style = verdict === "SUPPORTED" ? "badge-kredibel" : ["CONTRADICTED", "MISLEADING"].includes(verdict) ? "badge-hoaks" : "badge-perlu-dicek";
  return <span className={`meta-text inline-block px-3 py-2 font-bold text-[11px] ${style}`}>
    {verdict} · {LABELS[verdict]}
  </span>;
}

export default function VerdictCard({ result }: { result: AnalysisResult }) {
  return <section className="rule-top rule-bottom py-6 mb-6" aria-label="Hasil verifikasi">
    <p className="kicker mb-3">Hasil Verifikasi</p>
    <VerdictBadge verdict={result.verdict} />
    <p className="text-[15px] leading-relaxed mt-4">{result.reasoning}</p>
    {result.suggestion && <p className="text-[14px] text-[var(--color-meta)] mt-3">{result.suggestion}</p>}
    {!!result.limitations.length && <div className="mt-4 p-4 bg-[var(--color-highlight)]">
      <h3 className="section-label mb-2">Batasan Pemeriksaan</h3>
      <ul className="list-disc pl-5 space-y-1">{result.limitations.map((limit, i) => <li className="text-[13px]" key={i}>{limit}</li>)}</ul>
    </div>}
  </section>;
}
