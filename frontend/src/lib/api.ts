import axios from "axios";
import { AnalysisResult, NewsFeedResponse, NewsSummary } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 120s: AI analysis with grounding + possible rate-limit retry
});

/**
 * Token provider bridge. AuthProvider registers a function that returns the
 * current Firebase ID token (or null). Keeping this decoupled avoids importing
 * Firebase into every module that talks to the API.
 */
type TokenProvider = () => Promise<string | null>;
let tokenProvider: TokenProvider | null = null;

export function setTokenProvider(provider: TokenProvider | null): void {
  tokenProvider = provider;
}

// Attach the bearer token to every request when a user is signed in.
api.interceptors.request.use(async (config) => {
  if (tokenProvider) {
    const token = await tokenProvider();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export async function analyzeText(text: string): Promise<AnalysisResult> {
  const response = await api.post("/analyze", { text });
  return response.data;
}

export async function analyzeUrl(url: string): Promise<AnalysisResult> {
  const response = await api.post("/analyze", { url });
  return response.data;
}

export async function analyzeImage(imageDataUrl: string, caption: string): Promise<AnalysisResult> {
  const response = await api.post("/analyze", { image_data_url: imageDataUrl, ...(caption.trim() ? { text: caption.trim() } : {}) });
  return response.data;
}

export async function getNewsFeed(
  limit: number = 20,
  category: string = "terkini"
): Promise<NewsFeedResponse> {
  const response = await api.get("/news", { params: { limit, category } });
  return response.data;
}

export async function summarizeNewsArticle(newsId: string): Promise<NewsSummary> {
  const response = await api.get(`/news/${newsId}/summarize`);
  return response.data;
}
