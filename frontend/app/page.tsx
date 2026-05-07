"use client";

/* eslint-disable @next/next/no-img-element */

import { useMemo, useState } from "react";

import { useScrapeProduct } from "../hooks/useProducts";
import { mergeProducts, type Product } from "../lib/api";

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

function ProductCard({ product }: { product: Product }) {
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

  const { mutate: scrape, isPending: isScraping } = useScrapeProduct();

  const totalPages = Math.max(1, Math.ceil(products.length / ITEMS_PER_PAGE));
  const currentPage = Math.min(page, totalPages);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, products.length);
  const visibleProducts = useMemo(
    () => products.slice(startIndex, endIndex),
    [endIndex, products, startIndex],
  );

  function handleScrapeProduct(event: { preventDefault(): void }) {
    event.preventDefault();
    const trimmedAsin = asin.trim();
    if (!trimmedAsin) return;
    setNotice({ tone: "info", message: "Scraping product..." });
    scrape(
      { asin: trimmedAsin, geoLocation: geo.trim() },
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

  // function startCompetitorAnalysis(nextAsin: string) {
  //   setSelectedAsin(nextAsin);
  //   setAnalysis("");
  //   setNotice({ tone: "info", message: "Searching competitors..." });
  //   startAnalysis(
  //     { asin: nextAsin, domain, geoLocation: geo.trim() },
  //     {
  //       onSuccess: ({ competitors: found, fromCache }) => {
  //         setNotice({
  //           tone: fromCache ? "info" : "success",
  //           message: fromCache
  //             ? `Found ${found.length} existing competitors in the database.`
  //             : `Found ${found.length} competitors!`,
  //         });
  //       },
  //       onError: (error) => {
  //         setNotice({
  //           tone: "error",
  //           message: error instanceof Error ? error.message : "Competitor search failed.",
  //         });
  //       },
  //     },
  //   );
  // }

  // function refreshCompetitors() {
  //   if (!selectedAsin) return;
  //   setNotice({ tone: "info", message: "Refreshing competitors..." });
  //   refreshComps(
  //     { asin: selectedAsin, domain, geoLocation: geo.trim() },
  //     {
  //       onSuccess: (data) => {
  //         setNotice({ tone: "success", message: `Found ${data.length} competitors!` });
  //       },
  //       onError: (error) => {
  //         setNotice({
  //           tone: "error",
  //           message: error instanceof Error ? error.message : "Competitor refresh failed.",
  //         });
  //       },
  //     },
  //   );
  // }

  // function handleRunLlmAnalysis() {
  //   if (!selectedAsin) return;
  //   setNotice({ tone: "info", message: "Running LLM analysis..." });
  //   runAnalysis(selectedAsin, {
  //     onSuccess: (result) => {
  //       setAnalysis(result);
  //       setNotice({ tone: "success", message: "LLM analysis completed." });
  //     },
  //     onError: (error) => {
  //       setNotice({
  //         tone: "error",
  //         message: error instanceof Error ? error.message : "LLM analysis failed.",
  //       });
  //     },
  //   });
  // }

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
                <ProductCard key={product.asin} product={product} />
              ))}
            </div>
          </section>
        ) : null}

{/*
        {selectedAsin ? (
          <section className="flex flex-col gap-5 border-t border-zinc-800 pt-6">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-2xl font-semibold text-zinc-50">
                  Competitor analysis for {selectedAsin}
                </h2>
                <p className="mt-1 text-sm text-zinc-400">
                  {competitors.length > 0
                    ? `${competitors.length} competitors loaded.`
                    : "No competitors loaded yet."}
                </p>
              </div>

              <button
                type="button"
                onClick={refreshCompetitors}
                disabled={isSearchingCompetitors || isRefreshing}
                className="h-10 rounded-md border border-zinc-700 bg-zinc-900 px-4 text-sm font-semibold text-zinc-100 transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:text-zinc-500"
              >
                {isRefreshing ? "Refreshing..." : "Refresh Competitors"}
              </button>
            </div>

            <div className="flex flex-col gap-4 rounded-lg border border-zinc-800 bg-zinc-900 p-4 shadow-sm shadow-black/20 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-h-24 flex-1 rounded-md border border-zinc-800 bg-zinc-950 p-4">
                {analysis ? (
                  <div className="whitespace-pre-wrap text-sm leading-6 text-zinc-200">{analysis}</div>
                ) : (
                  <p className="text-sm text-zinc-500">Analysis output will appear here.</p>
                )}
              </div>

              <button
                type="button"
                onClick={handleRunLlmAnalysis}
                disabled={isAnalyzing}
                className="h-10 rounded-md bg-zinc-100 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
              >
                {isAnalyzing ? "Running LLM..." : "Analyze with LLM"}
              </button>
            </div>
          </section>
        ) : null} */}
      </div>
    </main>
  );
}
