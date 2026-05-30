import axios from "axios";
import { AnalysisResult, NewsFeedResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60s timeout for AI analysis
});

export async function analyzeText(text: string): Promise<AnalysisResult> {
  const response = await api.post("/analyze", { text });
  return response.data;
}

export async function analyzeUrl(url: string): Promise<AnalysisResult> {
  const response = await api.post("/analyze", { url });
  return response.data;
}

export async function getNewsFeed(limit: number = 20): Promise<NewsFeedResponse> {
  const response = await api.get("/news", { params: { limit } });
  return response.data;
}

export async function analyzeNewsArticle(newsId: string): Promise<AnalysisResult> {
  const response = await api.get(`/news/${newsId}/analyze`);
  return response.data;
}
