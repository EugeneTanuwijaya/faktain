"use client";

export interface NewsCategory {
  key: string;
  label: string;
}

export const NEWS_CATEGORIES: NewsCategory[] = [
  { key: "terkini", label: "Terkini" },
  { key: "nasional", label: "Nasional" },
  { key: "internasional", label: "Internasional" },
  { key: "ekonomi", label: "Ekonomi" },
  { key: "teknologi", label: "Teknologi" },
  { key: "olahraga", label: "Olahraga" },
  { key: "hiburan", label: "Hiburan" },
];

interface CategoryTabsProps {
  active: string;
  onChange: (key: string) => void;
  disabled?: boolean;
}

export default function CategoryTabs({
  active,
  onChange,
  disabled,
}: CategoryTabsProps) {
  return (
    <div className="cat-tabs rule-bottom" role="tablist" aria-label="Kategori berita">
      {NEWS_CATEGORIES.map((cat) => (
        <button
          key={cat.key}
          role="tab"
          aria-selected={active === cat.key}
          disabled={disabled}
          onClick={() => onChange(cat.key)}
          className={`cat-tab ${active === cat.key ? "cat-tab--active" : ""}`}
        >
          {cat.label}
        </button>
      ))}
    </div>
  );
}
