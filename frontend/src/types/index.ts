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

export type Verdict = "SUPPORTED" | "CONTRADICTED" | "MISLEADING" | "PARTIALLY_SUPPORTED" | "INSUFFICIENT_EVIDENCE";
export type InputType = "text" | "url" | "image";
export interface Evidence {
  source_id: string;
  title: string;
  url: string;
  excerpt: string;
}
export interface ClaimResult {
  claim: string;
  verdict: Verdict;
  reasoning: string;
  supporting_evidence: Evidence[];
  contradicting_evidence: Evidence[];
  limitations: string[];
}
export interface ImageContext {
  verdict: "VERIFIED_CONTEXT" | "MISLEADING_CONTEXT" | "INSUFFICIENT_EVIDENCE";
  reasoning: string;
  ocr_text: string;
  visual_description: string;
  evidence: Evidence[];
  limitations: string[];
}
export interface AnalysisResult {
  schema_version: "2.0";
  input_type: InputType;
  verdict: Verdict;
  reasoning: string;
  indicators: Indicator[];
  claims: ClaimResult[];
  image_context: ImageContext | null;
  limitations: string[];
  orchestration: "native" | "langflow" | "native_fallback";
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
