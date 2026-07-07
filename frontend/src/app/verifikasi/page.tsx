"use client";

import { useState } from "react";
import AnalysisForm from "@/components/AnalysisForm";
import VerdictCard from "@/components/VerdictCard";
import IndicatorList from "@/components/IndicatorList";
import SourcesList from "@/components/SourcesList";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useAuth } from "@/components/AuthProvider";
import { analyzeText, analyzeUrl } from "@/lib/api";
import { AnalysisResult } from "@/types";

export default function VerifikasiPage() {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { user, authConfigured, signInWithGoogle } = useAuth();

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
        const axiosErr = err as {
          response?: { status?: number; data?: { detail?: string } };
        };
        if (axiosErr.response?.status === 429) {
          setError(
            axiosErr.response?.data?.detail ||
              "Batas analisis tercapai. Silakan coba lagi nanti."
          );
        } else if (axiosErr.response?.status === 401) {
          setError("Sesi login berakhir. Silakan masuk kembali.");
        } else {
          setError(
            axiosErr.response?.data?.detail ||
              "Terjadi kesalahan saat menganalisis. Silakan coba lagi."
          );
        }
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
    <div>
      {/* Section header */}
      <div className="rule-bottom pb-4 mb-6">
        <p className="kicker mb-2">Alat Verifikasi</p>
        <h2
          className="headline text-4xl md:text-5xl"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Periksa Keaslian Berita
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-0">
        {/* Main Column */}
        <div className="md:pr-8 md:rule-right">
          {authConfigured && !user && (
            <div
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 mb-6"
              style={{ backgroundColor: "var(--color-highlight)" }}
            >
              <div>
                <p className="kicker mb-1">Akses Tamu</p>
                <p className="text-[13px] text-[var(--color-meta)] leading-relaxed">
                  Anda bisa memverifikasi tanpa masuk, dengan kuota harian
                  terbatas. Masuk dengan Google untuk kuota lebih tinggi dan
                  menyimpan riwayat analisis.
                </p>
              </div>
              <button
                type="button"
                onClick={() => signInWithGoogle()}
                className="meta-text px-4 py-2 bg-[var(--color-ink)] text-white border-none cursor-pointer hover:bg-[#333] transition-colors whitespace-nowrap"
              >
                MASUK DENGAN GOOGLE
              </button>
            </div>
          )}

          <AnalysisForm onSubmit={handleSubmit} isLoading={isLoading} />

          {isLoading && <LoadingSkeleton />}

          {error && (
            <div className="rule-top rule-bottom py-4 mb-6">
              <p
                className="meta-text mb-1"
                style={{ color: "var(--color-accent-red)" }}
              >
                Kesalahan
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

          {!result && !isLoading && !error && (
            <div className="rule-top pt-6 mt-2">
              <p className="kicker mb-2">Contoh</p>
              <p className="text-[15px] text-[var(--color-meta)] leading-relaxed">
                Coba tempel sebuah klaim viral, kutipan pesan berantai, atau URL
                artikel. Sistem akan menelusuri sumber tepercaya dan memberi
                skor kredibilitas.
              </p>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <aside className="md:pl-8 mt-8 md:mt-0">
          <div className="rule-bottom pb-3 mb-4">
            <h3 className="section-label">Cara Kerja</h3>
          </div>
          <ol className="space-y-4 text-[14px] text-[var(--color-meta)]">
            <li className="rule-bottom pb-3">
              <p className="kicker mb-1">Langkah 01</p>
              <p>Tempel teks berita atau URL artikel yang ingin diverifikasi.</p>
            </li>
            <li className="rule-bottom pb-3">
              <p className="kicker mb-1">Langkah 02</p>
              <p>
                Gemini AI menganalisis pola hoaks dan menelusuri sumber
                verifikasi di internet.
              </p>
            </li>
            <li className="rule-bottom pb-3">
              <p className="kicker mb-1">Langkah 03</p>
              <p>
                Dapatkan skor kredibilitas, indikator mencurigakan, dan sumber
                referensi.
              </p>
            </li>
          </ol>

          <div className="mt-6 p-4" style={{ backgroundColor: "var(--color-highlight)" }}>
            <p className="section-label mb-2">Catatan</p>
            <p className="text-[13px] text-[var(--color-meta)] leading-relaxed">
              Hasil AI bersifat bantuan, bukan vonis final. Selalu rujuk silang
              dengan media arus utama sebelum membagikan.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
