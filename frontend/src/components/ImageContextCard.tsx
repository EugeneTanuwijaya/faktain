import { ImageContext } from "@/types";
import { EvidenceList } from "@/components/SourcesList";

export default function ImageContextCard({ context }: { context: ImageContext }) {
  const color = context.verdict === "VERIFIED_CONTEXT" ? "badge-kredibel" : context.verdict === "MISLEADING_CONTEXT" ? "badge-hoaks" : "badge-perlu-dicek";
  return <section className="rule-bottom pb-6 mb-6" aria-label="Konteks gambar">
    <h3 className="headline text-xl mb-3">Pemeriksaan Konteks Gambar</h3>
    <span className={`meta-text inline-block px-3 py-2 text-[11px] ${color}`}>{context.verdict}</span>
    <p className="text-[14px] my-3">{context.reasoning}</p>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-4">
      <div><h4 className="section-label mb-2">Teks Terbaca (OCR)</h4><p className="text-[14px] whitespace-pre-wrap">{context.ocr_text || "Tidak ada teks yang berhasil dibaca."}</p></div>
      <div><h4 className="section-label mb-2">Observasi Visual</h4><p className="text-[14px]">{context.visual_description || "Observasi visual belum tersedia."}</p></div>
    </div>
    {!!context.evidence.length && <EvidenceList evidence={context.evidence} />}
    <ul className="list-disc pl-5 mt-4 text-[13px] text-[var(--color-meta)] space-y-1">{context.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul>
  </section>;
}
