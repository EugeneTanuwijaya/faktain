"use client";

import { useState } from "react";

interface AnalysisFormProps {
  onSubmit: (input: string, type: "text" | "url") => void;
  isLoading: boolean;
}

export default function AnalysisForm({ onSubmit, isLoading }: AnalysisFormProps) {
  const [input, setInput] = useState("");
  const [inputType, setInputType] = useState<"text" | "url">("text");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      onSubmit(input.trim(), inputType);
    }
  };

  const isUrl = (text: string) => {
    try {
      new URL(text);
      return true;
    } catch {
      return false;
    }
  };

  const handleInputChange = (value: string) => {
    setInput(value);
    if (isUrl(value)) {
      setInputType("url");
    } else {
      setInputType("text");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="mb-8">
      <div className="rule-bottom pb-4 mb-4">
        <h2
          className="headline text-2xl md:text-3xl mb-3"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Verifikasi Berita
        </h2>
        <p className="text-[15px] text-[var(--color-meta)] mb-4">
          Masukkan teks berita atau URL artikel yang ingin Anda verifikasi
          keasliannya. Sistem AI kami akan menganalisis dan membandingkan dengan
          sumber terpercaya.
        </p>
      </div>

      <div className="mb-4">
        <div className="flex gap-4 mb-3">
          <button
            type="button"
            onClick={() => setInputType("text")}
            className={`meta-text px-3 py-1 border transition-colors cursor-pointer ${
              inputType === "text"
                ? "border-[var(--color-rule)] bg-[var(--color-ink)] text-white"
                : "border-[var(--color-rule-light)]"
            }`}
          >
            Teks Berita
          </button>
          <button
            type="button"
            onClick={() => setInputType("url")}
            className={`meta-text px-3 py-1 border transition-colors cursor-pointer ${
              inputType === "url"
                ? "border-[var(--color-rule)] bg-[var(--color-ink)] text-white"
                : "border-[var(--color-rule-light)]"
            }`}
          >
            URL Artikel
          </button>
        </div>

        {inputType === "text" ? (
          <textarea
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            placeholder="Tempel teks berita yang ingin diverifikasi di sini..."
            rows={6}
            className="w-full p-4 border border-[var(--color-rule-light)] bg-white text-[15px] leading-relaxed resize-vertical focus:outline-none focus:border-[var(--color-rule)]"
            style={{ fontFamily: "'Georgia', serif" }}
            disabled={isLoading}
          />
        ) : (
          <input
            type="url"
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            placeholder="https://contoh.com/artikel-berita"
            className="w-full p-4 border border-[var(--color-rule-light)] bg-white text-[15px] focus:outline-none focus:border-[var(--color-rule)]"
            style={{ fontFamily: "'Inter', sans-serif" }}
            disabled={isLoading}
          />
        )}
      </div>

      <button
        type="submit"
        disabled={isLoading || !input.trim()}
        className="meta-text px-6 py-3 bg-[var(--color-ink)] text-white border-none cursor-pointer hover:bg-[#333] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? "MENGANALISIS..." : "ANALISIS SEKARANG"}
      </button>
    </form>
  );
}
