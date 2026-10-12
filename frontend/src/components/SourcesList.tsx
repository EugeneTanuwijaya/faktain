"use client";

import { ClaimResult, Evidence } from "@/types";
import { VerdictBadge } from "@/components/VerdictCard";

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  return <ul className="space-y-3">{evidence.map((item, i) => <li key={`${item.source_id}-${i}`} className="border-l-2 border-[var(--color-rule-light)] pl-3">
    <blockquote className="text-[14px] leading-relaxed whitespace-pre-wrap">&ldquo;{item.excerpt}&rdquo;</blockquote>
    <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-[13px] underline break-words">{item.title}</a>
    <p className="text-[11px] text-[var(--color-meta)] break-all mt-1">{item.url}</p>
  </li>)}</ul>;
}

export default function SourcesList({ claims }: { claims: ClaimResult[] }) {
  return <section aria-label="Verifikasi klaim">
    <h3 className="headline text-xl mb-4 rule-bottom pb-2">Klaim dan Evidence</h3>
    {!claims.length && <p className="text-[14px]">Belum ada klaim yang dapat diperiksa. Tambahkan caption atau teks yang lebih jelas.</p>}
    <div className="space-y-6">{claims.map((claim, i) => <article key={i} className="rule-bottom pb-6">
      <h4 className="headline text-lg mb-2">{i + 1}. {claim.claim}</h4>
      <VerdictBadge verdict={claim.verdict} />
      <p className="text-[14px] mt-3 mb-4">{claim.reasoning}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div><h5 className="section-label mb-2">Evidence Mendukung</h5>
          {claim.supporting_evidence.length ? <EvidenceList evidence={claim.supporting_evidence} /> : <p className="text-[13px] text-[var(--color-meta)]">Belum ada evidence pendukung yang diterima.</p>}</div>
        <div><h5 className="section-label mb-2">Evidence Membantah</h5>
          {claim.contradicting_evidence.length ? <EvidenceList evidence={claim.contradicting_evidence} /> : <p className="text-[13px] text-[var(--color-meta)]">Belum ada evidence pembantah yang diterima.</p>}</div>
      </div>
      {!!claim.limitations.length && <ul className="list-disc pl-5 mt-4 text-[13px] text-[var(--color-meta)] space-y-1">{claim.limitations.map((limit, j) => <li key={j}>{limit}</li>)}</ul>}
    </article>)}</div>
  </section>;
}
