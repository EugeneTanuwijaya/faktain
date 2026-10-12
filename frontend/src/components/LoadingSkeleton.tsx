"use client";

import { useEffect, useState } from "react";

// Stage messages shown in sequence so the (potentially long) wait feels alive.
// Free models can take 60-120s, so we set honest expectations and rotate
// through the actual pipeline stages.
const STAGES = [
  { at: 0, label: "Mengumpulkan konten..." },
  { at: 4, label: "Mencari sumber di internet..." },
  { at: 18, label: "Membandingkan dengan media terpercaya..." },
  { at: 35, label: "Menganalisis pola hoaks & memverifikasi klaim..." },
  { at: 60, label: "Menyusun kesimpulan... (model gratis bisa lebih lama)" },
];

export default function LoadingSkeleton() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const stage = [...STAGES].reverse().find((s) => elapsed >= s.at) ?? STAGES[0];

  return (
    <div className="rule-top rule-bottom py-6 mb-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="skeleton h-8 w-48 rounded-none" />
        <div className="skeleton h-10 w-16 rounded-none" />
      </div>
      <div className="space-y-3 mb-6">
        <div className="skeleton h-4 w-full rounded-none" />
        <div className="skeleton h-4 w-4/5 rounded-none" />
        <div className="skeleton h-4 w-3/5 rounded-none" />
      </div>
      <div className="rule-top pt-4">
        <div className="skeleton h-5 w-40 rounded-none mb-3" />
        <div className="space-y-2">
          <div className="skeleton h-3 w-full rounded-none" />
          <div className="skeleton h-3 w-5/6 rounded-none" />
          <div className="skeleton h-3 w-4/6 rounded-none" />
        </div>
      </div>

      <div className="mt-6 text-center">
        <p className="meta-text animate-pulse">{stage.label}</p>
        <p className="meta-text mt-1 text-[11px] text-[var(--color-meta)]">
          {elapsed}s berlalu &middot; analisis biasanya 30-90 detik
        </p>
      </div>
    </div>
  );
}
