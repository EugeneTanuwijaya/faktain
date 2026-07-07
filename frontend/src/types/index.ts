export interface Indicator {
  type: string;
  description: string;
  severity: "low" | "medium" | "high";
}

export interface VerifiedClaim {
  claim: string;
  status: "TERKONFIRMASI" | "DIBANTAH" | "TIDAK DAPAT DIVERIFIKASI";
  explanation: string;
  is_core?: boolean;
}

export interface Source {
  title: string;
  url: string;
  credibility: "TERPERCAYA" | "NETRAL" | "MERAGUKAN";
}

export interface AnalysisResult {
  confidence_score: number;
  verdict: "KREDIBEL" | "PERLU DICEK" | "KEMUNGKINAN HOAKS";
  reasoning: string;
  indicators: Indicator[];
  verified_claims: VerifiedClaim[];
  sources_found: Source[];
  suggestion: string;
  analyzed_text?: string;
}

export interface NewsItem {
  id: string;
  title: string;
  link: string;
  source: string;
  published: string;
  summary?: string;
  image_url?: string;
}

export interface NewsFeedResponse {
  articles: NewsItem[];
  last_updated: string;
}

export interface NewsSummary {
  id: string;
  title: string;
  source: string;
  original_url: string;
  summary: string;
}
