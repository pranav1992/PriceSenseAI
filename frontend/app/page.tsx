"use client";

/* eslint-disable @next/next/no-img-element */

import { useMemo, useState } from "react";

import { useRefreshCompetitors, useStartCompetitorAnalysis } from "../hooks/useCompetitors";
import { useScrapeProduct } from "../hooks/useProducts";
import { mergeProducts, type Product } from "../services";

const DOMAINS = ["com", "ca", "co.uk", "de", "fr", "it", "ae"] as const;
const ITEMS_PER_PAGE = 10;

type Domain = (typeof DOMAINS)[number];

type Notice = {
  tone: "info" | "success" | "error";
  message: string;
};

function formatPrice(product: Product) {
  const price = product.price === undefined || product.price === "" ? "-" : String(product.price);
  return product.currency ? `${product.currency} ${price}` : price;
}

function StarRating({ rating }: { rating?: number | string }) {
  const value = typeof rating === "string" ? parseFloat(rating) : rating;
  if (!value) return <span className="text-zinc-500">-</span>;
  const full = Math.floor(value);
  const half = value - full >= 0.5;
  return (
    <span className="flex items-center gap-1 text-sm text-amber-400">
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i}>{i < full ? "★" : i === full && half ? "½" : "☆"}</span>
      ))}
      <span className="ml-1 text-zinc-400">({value})</span>
    </span>
  );
}

function ProductCard({
  product,
  onAnalyze,
  isAnalyzing,
}: {
  product: Product;
  onAnalyze?: () => void;
  isAnalyzing?: boolean;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = product.images?.[0];
  const domainInfo = `amazon.${product.amazon_domain ?? "com"}`;

  return (
    <article className="grid gap-5 rounded-lg border border-zinc-800 bg-zinc-900 p-4 shadow-sm shadow-black/20 sm:grid-cols-[220px_1fr]">
      <div className="flex h-52 items-center justify-center overflow-hidden rounded-md border border-zinc-800 bg-zinc-950">
        {imageUrl && !imageFailed ? (
          <img
            src={imageUrl}
            alt={product.title ?? product.asin}
            className="h-full w-full object-contain"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="text-sm text-zinc-500">No image found.</span>
        )}
      </div>

      <div className="flex min-w-0 flex-col gap-4">
        <div>
          <h3 className="text-lg font-semibold text-zinc-50">{product.title ?? product.asin}</h3>
          <p className="mt-1 text-sm text-zinc-400">
            Domain: {domainInfo} | Geo Location: {product.geo_location ?? "-"}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2">
            <p className="text-xs font-medium uppercase text-zinc-400">Price</p>
            <p className="mt-1 text-lg font-semibold text-zinc-50">{formatPrice(product)}</p>
          </div>
          <div className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2">
            <p className="text-xs font-medium uppercase text-zinc-400">Brand</p>
            <p className="mt-1 truncate text-sm font-medium text-zinc-200">{product.brand ?? "-"}</p>
          </div>
          <div className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2">
            <p className="text-xs font-medium uppercase text-zinc-400">Product</p>
            <p className="mt-1 truncate text-sm font-medium text-zinc-200">{product.product ?? "-"}</p>
          </div>
        </div>

        {product.url ? (
          <a
            href={product.url}
            target="_blank"
            rel="noreferrer"
            className="truncate text-sm font-medium text-emerald-400 hover:text-emerald-300"
          >
            {product.url}
          </a>
        ) : null}

        <button
          type="button"
          onClick={onAnalyze}
          disabled={!onAnalyze || isAnalyzing}
          className="mt-auto h-10 w-full rounded-md bg-emerald-700 px-4 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
        >
          {isAnalyzing ? "Analyzing..." : "Start Analyzing Competitors"}
        </button>
      </div>
    </article>
  );
}

function CompetitorCard({ product }: { product: Product }) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = product.images?.[0];

  return (
    <article className="flex gap-4 rounded-lg border border-zinc-800 bg-zinc-900 p-4 shadow-sm shadow-black/20">
      <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-md border border-zinc-800 bg-zinc-950">
        {imageUrl && !imageFailed ? (
          <img
            src={imageUrl}
            alt={product.title ?? product.asin}
            className="h-full w-full object-contain"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="text-xs text-zinc-500">No image</span>
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <h4 className="line-clamp-2 text-sm font-semibold text-zinc-50">
            {product.title ?? product.asin}
          </h4>
          <span className="shrink-0 text-base font-bold text-emerald-400">{formatPrice(product)}</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-400">
          {product.brand ? <span>Brand: <span className="text-zinc-300">{product.brand}</span></span> : null}
          <span>ASIN: <span className="font-mono text-zinc-300">{product.asin}</span></span>
          <StarRating rating={product.rating} />
        </div>

        {product.url ? (
          <a
            href={product.url}
            target="_blank"
            rel="noreferrer"
            className="mt-auto w-fit truncate text-xs font-medium text-emerald-400 hover:text-emerald-300"
          >
            View on Amazon
          </a>
        ) : null}
      </div>
    </article>
  );
}

export default function Home() {
  const [asin, setAsin] = useState("");
  const [geo, setGeo] = useState("");
  const [domain, setDomain] = useState<Domain>("com");
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [competitorMap, setCompetitorMap] = useState<Record<string, Product[]>>({});
  const [activeCompetitorAsin, setActiveCompetitorAsin] = useState<string | null>(null);

  const { mutate: scrape, isPending: isScraping } = useScrapeProduct();
  const { mutate: startAnalysis, isPending: isAnalyzingCompetitors, variables: analyzingVars } =
    useStartCompetitorAnalysis();
  const { mutate: refresh, isPending: isRefreshing } = useRefreshCompetitors();

  const totalPages = Math.max(1, Math.ceil(products.length / ITEMS_PER_PAGE));
  const currentPage = Math.min(page, totalPages);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, products.length);
  const visibleProducts = useMemo(
    () => products.slice(startIndex, endIndex),
    [endIndex, products, startIndex],
  );

  const activeProduct = products.find((p) => p.asin === activeCompetitorAsin);
  const activeCompetitors = activeCompetitorAsin ? (competitorMap[activeCompetitorAsin] ?? []) : [];

  function handleScrapeProduct(event: { preventDefault(): void }) {
    event.preventDefault();
    const trimmedAsin = asin.trim();
    if (!trimmedAsin) return;
    setNotice({ tone: "info", message: "Scraping product..." });
    scrape(
      { asin: trimmedAsin, geoLocation: geo.trim(), domain },
      {
        onSuccess: (scrapedProducts) => {
          if (scrapedProducts.length === 0) {
            setNotice({ tone: "error", message: "No product details were returned." });
            return;
          }

          setProducts((currentProducts) => mergeProducts(currentProducts, scrapedProducts));
          setPage(1);
          setNotice({ tone: "success", message: "Product scraped successfully!" });
        },
        onError: (error) => {
          setNotice({
            tone: "error",
            message: error instanceof Error ? error.message : "Product scraping failed.",
          });
        },
      },
    );
  }

  function handleRefreshCompetitors() {
    if (!activeCompetitorAsin) return;
    setNotice({ tone: "info", message: "Refreshing competitors..." });
    refresh(
      { asin: activeCompetitorAsin, domain, geoLocation: geo.trim() },
      {
        onSuccess: (competitors) => {
          setCompetitorMap((prev) => ({ ...prev, [activeCompetitorAsin]: competitors }));
          setNotice({ tone: "success", message: `Refreshed — ${competitors.length} competitors found.` });
        },
        onError: (error) => {
          setNotice({
            tone: "error",
            message: error instanceof Error ? error.message : "Refresh failed.",
          });
        },
      },
    );
  }

  function handleAnalyze(productAsin: string) {
    setNotice({ tone: "info", message: "Searching for competitors..." });
    startAnalysis(
      { asin: productAsin, domain, geoLocation: geo.trim() },
      {
        onSuccess: ({ competitors }) => {
          setCompetitorMap((prev) => ({ ...prev, [productAsin]: competitors }));
          setActiveCompetitorAsin(productAsin);
          setNotice({
            tone: "success",
            message: `Found ${competitors.length} competitors.`,
          });
        },
        onError: (error) => {
          setNotice({
            tone: "error",
            message: error instanceof Error ? error.message : "Competitor search failed.",
          });
        },
      },
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-2 border-b border-zinc-800 pb-6">
          <h1 className="text-3xl font-semibold text-zinc-50">Amazon Competitor Analysis</h1>
          <p className="text-sm text-zinc-400">Enter your ASIN to get product insights.</p>
        </header>

        <form
          onSubmit={handleScrapeProduct}
          className="flex flex-col gap-4 rounded-lg border border-zinc-800 bg-zinc-900 p-4 shadow-sm shadow-black/20"
        >
          <label className="flex flex-col gap-2 text-sm font-medium text-zinc-300">
            ASIN
            <input
              value={asin}
              onChange={(event) => setAsin(event.target.value)}
              placeholder="e.g., B0CX23VSAS"
              className="h-11 rounded-md border border-zinc-700 bg-zinc-950 px-3 text-zinc-50 outline-none transition placeholder:text-zinc-500 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-400/20"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm font-medium text-zinc-300">
            Zip/Postal Code
            <input
              value={geo}
              onChange={(event) => setGeo(event.target.value)}
              placeholder="e.g., 83980"
              className="h-11 rounded-md border border-zinc-700 bg-zinc-950 px-3 text-zinc-50 outline-none transition placeholder:text-zinc-500 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-400/20"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm font-medium text-zinc-300">
            Domain
            <select
              value={domain}
              onChange={(event) => setDomain(event.target.value as Domain)}
              className="h-11 rounded-md border border-zinc-700 bg-zinc-950 px-3 text-zinc-50 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-400/20"
            >
              {DOMAINS.map((domainOption) => (
                <option key={domainOption} value={domainOption}>
                  {domainOption}
                </option>
              ))}
            </select>
          </label>

          <div className="flex">
            <button
              type="submit"
              disabled={!asin.trim() || isScraping}
              className="h-11 w-full rounded-md bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-zinc-400"
            >
              {isScraping ? "Scraping..." : "Scrape Product"}
            </button>
          </div>
        </form>

        {notice ? (
          <div
            className={[
              "rounded-md border px-4 py-3 text-sm font-medium",
              notice.tone === "success"
                ? "border-emerald-500/30 bg-emerald-950/50 text-emerald-200"
                : "",
              notice.tone === "info" ? "border-sky-500/30 bg-sky-950/50 text-sky-200" : "",
              notice.tone === "error" ? "border-red-500/30 bg-red-950/50 text-red-200" : "",
            ].join(" ")}
          >
            {notice.message}
          </div>
        ) : null}

        {products.length > 0 ? (
          <section className="flex flex-col gap-5">
            <div className="flex flex-col justify-between gap-4 border-b border-zinc-800 pb-4 sm:flex-row sm:items-end">
              <div>
                <h2 className="text-2xl font-semibold text-zinc-50">Product Scraped</h2>
                <p className="mt-1 text-sm text-zinc-400">
                  Showing {startIndex + 1} - {endIndex} of {products.length} products
                </p>
              </div>

              <label className="flex w-full max-w-36 flex-col gap-2 text-sm font-medium text-zinc-300">
                Page
                <input
                  type="number"
                  min={1}
                  max={totalPages}
                  value={currentPage}
                  onChange={(event) => {
                    const nextPage = Number(event.target.value);
                    setPage(Number.isFinite(nextPage) ? Math.min(Math.max(1, nextPage), totalPages) : 1);
                  }}
                  className="h-10 rounded-md border border-zinc-700 bg-zinc-950 px-3 text-zinc-50 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-400/20"
                />
              </label>
            </div>

            <div className="flex flex-col gap-4">
              {visibleProducts.map((product) => (
                <ProductCard
                  key={product.asin}
                  product={product}
                  isAnalyzing={isAnalyzingCompetitors && analyzingVars?.asin === product.asin}
                  onAnalyze={() => handleAnalyze(product.asin)}
                />
              ))}
            </div>
          </section>
        ) : null}

        {activeCompetitorAsin && activeCompetitors.length > 0 ? (
          <section className="flex flex-col gap-5 border-t border-zinc-800 pt-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold text-zinc-50">Competitors</h2>
                <p className="mt-1 text-sm text-zinc-400">
                  {activeCompetitors.length} results for{" "}
                  <span className="text-zinc-300">{activeProduct?.title ?? activeCompetitorAsin}</span>
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleRefreshCompetitors}
                  disabled={isRefreshing}
                  className="h-9 rounded-md border border-zinc-700 bg-zinc-800 px-4 text-sm font-medium text-zinc-200 transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isRefreshing ? "Refreshing..." : "Refresh Competitors"}
                </button>
                <button
                  type="button"
                  onClick={() => setActiveCompetitorAsin(null)}
                  className="text-sm text-zinc-500 hover:text-zinc-300"
                >
                  Dismiss
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-3">
              {activeCompetitors.map((competitor) => (
                <CompetitorCard key={competitor.asin} product={competitor} />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
