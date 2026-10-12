"use client";

import Image from "next/image";
import { useRef, useState } from "react";
import { InputType } from "@/types";

interface AnalysisFormProps {
  onSubmit: (input: string, type: InputType, imageDataUrl?: string) => void;
  isLoading: boolean;
  initialInputType?: InputType;
}

export default function AnalysisForm({ onSubmit, isLoading, initialInputType = "text" }: AnalysisFormProps) {
  const [input, setInput] = useState("");
  const [inputType, setInputType] = useState<InputType>(initialInputType);
  const [caption, setCaption] = useState("");
  const [imageDataUrl, setImageDataUrl] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const selection = useRef(0);
  const fieldClass = "w-full p-4 border border-[var(--color-rule-light)] bg-white text-[15px] focus:outline-none focus:border-[var(--color-rule)]";

  const selectImage = (file?: File) => {
    const current = ++selection.current;
    setImageDataUrl("");
    setFileError(null);
    setReading(false);
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setFileError("Gunakan gambar JPEG, PNG, atau WebP.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setFileError("Ukuran gambar maksimal 5 MiB.");
      return;
    }
    setReading(true);
    const reader = new FileReader();
    reader.onload = () => {
      if (selection.current !== current) return;
      setImageDataUrl(String(reader.result));
      setReading(false);
    };
    reader.onerror = () => {
      if (selection.current !== current) return;
      setFileError("Gambar tidak dapat dibaca. Pilih ulang file.");
      setReading(false);
    };
    reader.readAsDataURL(file);
  };

  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      if (inputType === "image" && imageDataUrl) onSubmit(caption.trim(), inputType, imageDataUrl);
      else if (input.trim()) onSubmit(input.trim(), inputType);
    }} className="mb-8">
      <div className="rule-bottom pb-4 mb-4">
        <p className="kicker mb-2">Masukkan Informasi</p>
        <h2 className="headline text-2xl md:text-3xl mb-3">Verifikasi Berbasis Bukti</h2>
        <p className="text-[15px] text-[var(--color-meta)]">Cek berita dari teks atau tautan, atau unggah screenshot untuk verifikasi timpa teks. Setiap kesimpulan disertai bukti dan batasannya.</p>
      </div>
      <div className="flex flex-wrap gap-3 mb-4" role="group" aria-label="Jenis input">
        {([["text", "Teks Berita"], ["url", "URL Artikel"], ["image", "Verifikasi Timpa Teks"]] as const).map(([type, label]) => (
          <button key={type} type="button" aria-pressed={inputType === type} disabled={isLoading}
            onClick={() => setInputType(type)}
            className={`meta-text px-3 py-2 border cursor-pointer ${inputType === type ? "bg-[var(--color-ink)] text-white border-[var(--color-rule)]" : "border-[var(--color-rule-light)]"}`}>
            {label}
          </button>
        ))}
      </div>
      {inputType === "image" ? (
        <div className="space-y-3 mb-4">
          <p className="text-[15px] leading-relaxed">Benarkah sumber aslinya menulis demikian? Unggah screenshot berita, unggahan, atau kutipan yang Anda ragukan. Foto dengan klaim juga bisa diperiksa.</p>
          <label htmlFor="verification-image" className="section-label block">Gambar atau screenshot</label>
          <input id="verification-image" type="file" accept="image/jpeg,image/png,image/webp" disabled={isLoading}
            onChange={(e) => selectImage(e.target.files?.[0])} className={fieldClass} />
          <p className="text-[13px] text-[var(--color-meta)]">JPEG, PNG, atau WebP; maksimal 5 MiB dan 16 megapiksel. Gunakan teks yang terbaca. Gambar dikirim ke layanan AI untuk dianalisis.</p>
          {reading && <p role="status">Membaca gambar...</p>}
          {fileError && <p role="alert" className="text-[var(--color-accent-red)]">{fileError}</p>}
          {imageDataUrl && <Image src={imageDataUrl} alt="Pratinjau gambar yang akan diverifikasi" width={600} height={400}
            unoptimized className="max-h-64 w-auto max-w-full object-contain border border-[var(--color-rule-light)]" />}
          <label htmlFor="verification-caption" className="section-label block">Caption atau klaim (opsional)</label>
          <textarea id="verification-caption" value={caption} maxLength={8000} rows={3} disabled={isLoading}
            onChange={(e) => setCaption(e.target.value)} placeholder="Contoh: Apakah media ini benar menerbitkan judul tersebut?" className={fieldClass} />
          <p className="text-[13px] text-[var(--color-meta)] leading-relaxed">Klaim yang salah belum membuktikan teks telah diedit. Jika sumber asli belum ditemukan, keaslian tulisan belum dapat dipastikan. Pemeriksaan ini menelusuri klaim dan konteks, bukan analisis forensik penyuntingan.</p>
        </div>
      ) : inputType === "text" ? (
        <div className="mb-4">
          <label htmlFor="verification-text" className="section-label block mb-2">Teks berita</label>
          <textarea id="verification-text" value={input} maxLength={20000} rows={6} disabled={isLoading}
            onChange={(e) => {
              const value = e.target.value;
              setInput(value);
              if (/^https?:\/\/\S+$/.test(value.trim())) setInputType("url");
            }} placeholder="Tempel teks berita yang ingin diverifikasi di sini..." className={fieldClass} />
        </div>
      ) : (
        <div className="mb-4">
          <label htmlFor="verification-url" className="section-label block mb-2">URL artikel</label>
          <input id="verification-url" type="url" value={input} maxLength={2048} disabled={isLoading}
            onChange={(e) => setInput(e.target.value)} placeholder="https://contoh.com/artikel-berita" className={fieldClass} />
        </div>
      )}
      <button type="submit" disabled={isLoading || reading || (inputType === "image" ? !imageDataUrl : !input.trim())}
        className="meta-text px-6 py-3 bg-[var(--color-ink)] text-white cursor-pointer hover:bg-[#333] disabled:opacity-50 disabled:cursor-not-allowed">
        {isLoading ? "MEMERIKSA EVIDENCE..." : "VERIFIKASI SEKARANG"}
      </button>
      <p className="text-[13px] text-[var(--color-meta)] mt-3">Pemeriksaan dapat memakan waktu. Jika bukti belum cukup, sistem menyatakan INSUFFICIENT_EVIDENCE.</p>
    </form>
  );
}
