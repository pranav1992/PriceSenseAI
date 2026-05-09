import { requestJson } from "./http";

export type PriceStats = {
  median: number;
  avg: number;
  min: number;
  max: number;
  count: number;
};

export type PriceSuggestion = {
  suggested_price: number;
  discount_pct: number;
  price_position: "above_market" | "at_market" | "below_market";
};

export type StockSignal = {
  level: "in_stock" | "low_stock" | "out_of_stock" | "unknown";
  severity: "ok" | "warning" | "critical" | "info";
  action: string | null;
};

export type AnalysisResult = {
  asin: string;
  current_price: number | null;
  price_stats: PriceStats | null;
  suggestion: PriceSuggestion | null;
  stock_signal: StockSignal;
};

export type InsightsResult = {
  asin: string;
  price_analysis: string;
  discount_recommendation: string;
  competitive_positioning: string;
};

export async function getAnalysis(asin: string): Promise<AnalysisResult> {
  return requestJson<AnalysisResult>(`/api/analysis/${encodeURIComponent(asin)}`);
}

export async function getAiInsights(asin: string): Promise<InsightsResult> {
  return requestJson<InsightsResult>(
    `/api/analysis/${encodeURIComponent(asin)}/insights`,
    { method: "POST" },
  );
}
