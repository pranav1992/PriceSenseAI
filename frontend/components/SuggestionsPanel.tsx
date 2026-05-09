"use client";

import { useAiInsights, useAnalysis } from "../hooks/useAnalysis";
import type { InsightsResult, PriceSuggestion, StockSignal } from "../services/analysis";

const POSITION_LABEL: Record<string, string> = {
  above_market: "Above Market",
  at_market: "At Market",
  below_market: "Below Market",
};

const POSITION_CLASSES: Record<string, string> = {
  above_market: "border-amber-500/30 bg-amber-950/40 text-amber-300",
  at_market: "border-emerald-500/30 bg-emerald-950/40 text-emerald-300",
  below_market: "border-sky-500/30 bg-sky-950/40 text-sky-300",
};

const STOCK_DOT: Record<string, string> = {
  in_stock: "bg-emerald-400",
  low_stock: "bg-amber-400",
  out_of_stock: "bg-red-400",
  unknown: "bg-zinc-400",
};

const STOCK_TEXT: Record<string, string> = {
  in_stock: "text-emerald-300",
  low_stock: "text-amber-300",
  out_of_stock: "text-red-300",
  unknown: "text-zinc-400",
};

function StockBadge({ signal }: { signal: StockSignal }) {
  const dot = STOCK_DOT[signal.level] ?? "bg-zinc-400";
  const text = STOCK_TEXT[signal.level] ?? "text-zinc-400";
  const label = signal.level.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <div className="flex flex-col gap-1">
      <span className={`flex items-center gap-2 text-sm font-semibold ${text}`}>
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        {label}
      </span>
      {signal.action ? (
        <span className="text-xs text-zinc-400">{signal.action}</span>
      ) : null}
    </div>
  );
}

function PriceSuggestionBlock({
  suggestion,
  currency,
}: {
  suggestion: PriceSuggestion;
  currency: string;
}) {
  const positionClass =
    POSITION_CLASSES[suggestion.price_position] ?? "border-zinc-700 bg-zinc-900 text-zinc-300";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${positionClass}`}
        >
          {POSITION_LABEL[suggestion.price_position] ?? suggestion.price_position}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2">
          <p className="text-xs font-medium uppercase text-zinc-500">Suggested Price</p>
          <p className="mt-1 text-lg font-bold text-zinc-50">
            {currency} {suggestion.suggested_price.toFixed(2)}
          </p>
        </div>
        {suggestion.discount_pct > 0 ? (
          <div className="rounded-md border border-amber-500/20 bg-amber-950/30 px-3 py-2">
            <p className="text-xs font-medium uppercase text-amber-500/70">Discount Needed</p>
            <p className="mt-1 text-lg font-bold text-amber-300">
              -{suggestion.discount_pct.toFixed(1)}%
            </p>
          </div>
        ) : (
          <div className="rounded-md border border-emerald-500/20 bg-emerald-950/30 px-3 py-2">
            <p className="text-xs font-medium uppercase text-emerald-500/70">Price Status</p>
            <p className="mt-1 text-sm font-semibold text-emerald-300">Competitively priced</p>
          </div>
        )}
      </div>
    </div>
  );
}

function InsightsBlock({ insights }: { insights: InsightsResult }) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-zinc-700 bg-zinc-950 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">AI Insights</p>
      {insights.price_analysis ? (
        <div>
          <p className="text-xs font-medium text-zinc-400">Price Analysis</p>
          <p className="mt-1 text-sm text-zinc-200">{insights.price_analysis}</p>
        </div>
      ) : null}
      {insights.discount_recommendation ? (
        <div>
          <p className="text-xs font-medium text-zinc-400">Discount Recommendation</p>
          <p className="mt-1 text-sm text-zinc-200">{insights.discount_recommendation}</p>
        </div>
      ) : null}
      {insights.competitive_positioning ? (
        <div>
          <p className="text-xs font-medium text-zinc-400">Competitive Positioning</p>
          <p className="mt-1 text-sm text-zinc-200">{insights.competitive_positioning}</p>
        </div>
      ) : null}
    </div>
  );
}

export function SuggestionsPanel({
  asin,
  currency = "USD",
}: {
  asin: string;
  currency?: string;
}) {
  const { data: analysis, isLoading, error } = useAnalysis(asin);
  const {
    mutate: fetchInsights,
    isPending: isLoadingInsights,
    data: insights,
  } = useAiInsights();

  if (isLoading) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-400">
        Loading price analysis...
      </div>
    );
  }

  if (error || !analysis) return null;

  const noCompetitorData = !analysis.price_stats;

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-zinc-800 bg-zinc-900 p-4 shadow-sm shadow-black/20">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Price Intelligence
        </h3>
        {analysis.price_stats ? (
          <span className="text-xs text-zinc-500">
            {analysis.price_stats.count} competitors · Range{" "}
            {currency} {analysis.price_stats.min.toFixed(2)} –{" "}
            {currency} {analysis.price_stats.max.toFixed(2)}
          </span>
        ) : null}
      </div>

      {noCompetitorData ? (
        <p className="text-sm text-zinc-500">
          No competitor prices available. Fetch competitors first to see price suggestions.
        </p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
            {analysis.suggestion ? (
              <PriceSuggestionBlock
                suggestion={analysis.suggestion}
                currency={currency}
              />
            ) : null}
            <div className="flex flex-col justify-center gap-1">
              <p className="text-xs font-medium uppercase text-zinc-500">Stock Status</p>
              <StockBadge signal={analysis.stock_signal} />
            </div>
          </div>

          {insights ? (
            <InsightsBlock insights={insights} />
          ) : (
            <button
              type="button"
              onClick={() => fetchInsights(asin)}
              disabled={isLoadingInsights}
              className="h-9 w-full rounded-md border border-zinc-700 bg-zinc-800 px-4 text-sm font-medium text-zinc-200 transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoadingInsights ? "Getting AI Insights..." : "Get AI Insights"}
            </button>
          )}
        </>
      )}
    </div>
  );
}
