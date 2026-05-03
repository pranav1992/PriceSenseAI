"use client";

/* eslint-disable @next/next/no-img-element */

import { FormEvent, useEffect, useMemo, useState } from "react";

const DOMAINS = ["com", "ca", "co.uk", "de", "fr", "it", "ae"] as const;
const ITEMS_PER_PAGE = 10;
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

const API_ENDPOINTS = {
  products: "/api/products",
  scrapeProduct: "/api/products/scrape",
  competitors: "/api/competitors",
  fetchCompetitors: "/api/competitors/fetch",
  analyzeCompetitors: "/api/analysis/competitors",
};

type Domain = (typeof DOMAINS)[number];

type Product = {
  asin: string;
  parent_asin?: string;
  title?: string;
  images?: string[];
  currency?: string;
  price?: number | string;
  brand?: string;
  product?: string;
  amazon_domain?: string;
  geo_location?: string;
  url?: string;
};

type Notice = {
  tone: "info" | "success" | "error";
  message: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function normalizeProduct(value: unknown): Product | null {
  if (!isRecord(value)) {
    return null;
  }

  const asin = stringValue(value.asin);

  if (!asin) {
    return null;
  }

  return {
    asin,
    parent_asin: stringValue(value.parent_asin),
    title: stringValue(value.title),
    images: Array.isArray(value.images)
      ? value.images.filter((image): image is string => typeof image === "string")
      : [],
    currency: stringValue(value.currency),
    price:
      typeof value.price === "number" || typeof value.price === "string"
        ? value.price
        : undefined,
    brand: stringValue(value.brand),
    product: stringValue(value.product),
    amazon_domain: stringValue(value.amazon_domain),
    geo_location: stringValue(value.geo_location),
    url: stringValue(value.url),
  };
}

function productsFromPayload(payload: unknown): Product[] {
  if (Array.isArray(payload)) {
    return payload.map(normalizeProduct).filter((product): product is Product => product !== null);
  }

  if (!isRecord(payload)) {
    return [];
  }

  const listKeys = ["products", "competitors", "items", "results"];

  for (const key of listKeys) {
    const value = payload[key];

    if (Array.isArray(value)) {
      return value.map(normalizeProduct).filter((product): product is Product => product !== null);
    }
  }

  const product = normalizeProduct(payload.product) ?? normalizeProduct(payload);
  return product ? [product] : [];
}

function mergeProducts(existing: Product[], incoming: Product[]) {
  const productsByAsin = new Map(existing.map((product) => [product.asin, product]));

  for (const product of incoming) {
    productsByAsin.set(product.asin, { ...productsByAsin.get(product.asin), ...product });
  }

  return Array.from(productsByAsin.values());
}

function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  const text = await response.text();

  if (!response.ok) {
    throw new Error(readErrorMessage(text, response.status, path));
  }

  if (!text) {
    return null as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}

function readErrorMessage(text: string, status: number, path: string) {
  if (text) {
    try {
      const payload = JSON.parse(text) as unknown;

      if (isRecord(payload)) {
        const detail = stringValue(payload.detail) ?? stringValue(payload.message) ?? stringValue(payload.error);

        if (detail) {
          return detail;
        }
      }
    } catch {
      if (!text.trim().startsWith("<") && text.length < 180) {
        return text;
      }
    }
  }

  return `Request to ${path} failed with status ${status}.`;
}

async function getProducts() {
  const payload = await requestJson<unknown>(API_ENDPOINTS.products);
  return productsFromPayload(payload);
}

async function scrapeAndStoreProduct(asin: string, geo: string, domain: Domain) {
  const payload = await requestJson<unknown>(API_ENDPOINTS.scrapeProduct, {
    method: "POST",
    body: JSON.stringify({ asin, geo, domain }),
  });

  return productsFromPayload(payload);
}

async function getExistingCompetitors(parentAsin: string) {
  const params = new URLSearchParams({ parent_asin: parentAsin });
  const payload = await requestJson<unknown>(`${API_ENDPOINTS.competitors}?${params.toString()}`);
  return productsFromPayload(payload);
}

async function fetchAndStoreCompetitors(asin: string, domain: Domain, geo: string) {
  const payload = await requestJson<unknown>(API_ENDPOINTS.fetchCompetitors, {
    method: "POST",
    body: JSON.stringify({ asin, domain, geo }),
  });

  return productsFromPayload(payload);
}

async function analyzeCompetitors(asin: string) {
  const payload = await requestJson<unknown>(API_ENDPOINTS.analyzeCompetitors, {
    method: "POST",
    body: JSON.stringify({ asin }),
  });

  if (typeof payload === "string") {
    return payload;
  }

  if (isRecord(payload)) {
    return (
      stringValue(payload.analysis) ??
      stringValue(payload.markdown) ??
      stringValue(payload.result) ??
      "No analysis returned."
    );
  }

  return "No analysis returned.";
}

function formatPrice(product: Product) {
  const price = product.price === undefined || product.price === "" ? "-" : String(product.price);
  return product.currency ? `${product.currency} ${price}` : price;
}

function ProductCard({
  product,
  isSelected,
  onAnalyze,
}: {
  product: Product;
  isSelected: boolean;
  onAnalyze: (asin: string) => void;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = product.images?.[0];
  const domainInfo = `amazon.${product.amazon_domain ?? "com"}`;

  return (
    <article className="grid gap-5 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm sm:grid-cols-[220px_1fr]">
      <div className="flex h-52 items-center justify-center overflow-hidden rounded-md border border-zinc-200 bg-zinc-50">
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
          <h3 className="text-lg font-semibold text-zinc-950">{product.title ?? product.asin}</h3>
          <p className="mt-1 text-sm text-zinc-500">
            Domain: {domainInfo} | Geo Location: {product.geo_location ?? "-"}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
            <p className="text-xs font-medium uppercase text-zinc-500">Price</p>
            <p className="mt-1 text-lg font-semibold text-zinc-950">{formatPrice(product)}</p>
          </div>
          <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
            <p className="text-xs font-medium uppercase text-zinc-500">Brand</p>
            <p className="mt-1 truncate text-sm font-medium text-zinc-900">{product.brand ?? "-"}</p>
          </div>
          <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
            <p className="text-xs font-medium uppercase text-zinc-500">Product</p>
            <p className="mt-1 truncate text-sm font-medium text-zinc-900">{product.product ?? "-"}</p>
          </div>
        </div>

        {product.url ? (
          <a
            href={product.url}
            target="_blank"
            rel="noreferrer"
            className="truncate text-sm font-medium text-emerald-700 hover:text-emerald-800"
          >
            {product.url}
          </a>
        ) : null}

        <div>
          <button
            type="button"
            onClick={() => onAnalyze(product.asin)}
            className="rounded-md bg-zinc-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-400"
            disabled={isSelected}
          >
            {isSelected ? "Analyzing competitors" : "Start analyzing competitors"}
          </button>
        </div>
      </div>
    </article>
  );
}

export default function Home() {
  const [asin, setAsin] = useState("");
  const [geo, setGeo] = useState("");
  const [domain, setDomain] = useState<Domain>("com");
  const [products, setProducts] = useState<Product[]>([]);
  const [competitors, setCompetitors] = useState<Product[]>([]);
  const [selectedAsin, setSelectedAsin] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState("");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [isScraping, setIsScraping] = useState(false);
  const [isSearchingCompetitors, setIsSearchingCompetitors] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const totalPages = Math.max(1, Math.ceil(products.length / ITEMS_PER_PAGE));
  const currentPage = Math.min(page, totalPages);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, products.length);
  const visibleProducts = useMemo(
    () => products.slice(startIndex, endIndex),
    [endIndex, products, startIndex],
  );

  useEffect(() => {
    let isMounted = true;

    async function loadProducts() {
      try {
        const loadedProducts = await getProducts();

        if (isMounted) {
          setProducts(loadedProducts);
        }
      } catch {
        if (isMounted) {
          setProducts([]);
        }
      }
    }

    void loadProducts();

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleScrapeProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedAsin = asin.trim();
    const trimmedGeo = geo.trim();

    if (!trimmedAsin) {
      return;
    }

    setIsScraping(true);
    setNotice({ tone: "info", message: "Scraping product..." });

    try {
      const scrapedProducts = await scrapeAndStoreProduct(trimmedAsin, trimmedGeo, domain);

      if (scrapedProducts.length > 0) {
        setProducts((currentProducts) => mergeProducts(currentProducts, scrapedProducts));
      } else {
        setProducts(await getProducts());
      }

      setPage(1);
      setNotice({ tone: "success", message: "Product scraped successfully!" });
    } catch (error) {
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "Product scraping failed.",
      });
    } finally {
      setIsScraping(false);
    }
  }

  async function startCompetitorAnalysis(nextAsin: string) {
    setSelectedAsin(nextAsin);
    setCompetitors([]);
    setAnalysis("");
    setIsSearchingCompetitors(true);
    setNotice({ tone: "info", message: "Searching competitors..." });

    try {
      const existingCompetitors = await getExistingCompetitors(nextAsin);

      if (existingCompetitors.length > 0) {
        setCompetitors(existingCompetitors);
        setNotice({
          tone: "info",
          message: `Found ${existingCompetitors.length} existing competitors in the database.`,
        });
        return;
      }

      const fetchedCompetitors = await fetchAndStoreCompetitors(nextAsin, domain, geo.trim());
      setCompetitors(fetchedCompetitors);
      setNotice({ tone: "success", message: `Found ${fetchedCompetitors.length} competitors!` });
    } catch (error) {
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "Competitor search failed.",
      });
    } finally {
      setIsSearchingCompetitors(false);
    }
  }

  async function refreshCompetitors() {
    if (!selectedAsin) {
      return;
    }

    setIsSearchingCompetitors(true);
    setNotice({ tone: "info", message: "Refreshing competitors..." });

    try {
      const fetchedCompetitors = await fetchAndStoreCompetitors(selectedAsin, domain, geo.trim());
      setCompetitors(fetchedCompetitors);
      setNotice({ tone: "success", message: `Found ${fetchedCompetitors.length} competitors!` });
    } catch (error) {
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "Competitor refresh failed.",
      });
    } finally {
      setIsSearchingCompetitors(false);
    }
  }

  async function runLlmAnalysis() {
    if (!selectedAsin) {
      return;
    }

    setIsAnalyzing(true);
    setNotice({ tone: "info", message: "Running LLM analysis..." });

    try {
      const nextAnalysis = await analyzeCompetitors(selectedAsin);
      setAnalysis(nextAnalysis);
      setNotice({ tone: "success", message: "LLM analysis completed." });
    } catch (error) {
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "LLM analysis failed.",
      });
    } finally {
      setIsAnalyzing(false);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-2 border-b border-zinc-200 pb-6">
          <h1 className="text-3xl font-semibold text-zinc-950">Amazon Competitor Analysis</h1>
          <p className="text-sm text-zinc-600">Enter your ASIN to get product insights.</p>
        </header>

        <form
          onSubmit={handleScrapeProduct}
          className="grid gap-4 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm lg:grid-cols-[1fr_1fr_180px_auto]"
        >
          <label className="flex flex-col gap-2 text-sm font-medium text-zinc-700">
            ASIN
            <input
              value={asin}
              onChange={(event) => setAsin(event.target.value)}
              placeholder="e.g., B0CX23VSAS"
              className="h-11 rounded-md border border-zinc-300 px-3 text-zinc-950 outline-none transition focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm font-medium text-zinc-700">
            Zip/Postal Code
            <input
              value={geo}
              onChange={(event) => setGeo(event.target.value)}
              placeholder="e.g., 83980"
              className="h-11 rounded-md border border-zinc-300 px-3 text-zinc-950 outline-none transition focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm font-medium text-zinc-700">
            Domain
            <select
              value={domain}
              onChange={(event) => setDomain(event.target.value as Domain)}
              className="h-11 rounded-md border border-zinc-300 bg-white px-3 text-zinc-950 outline-none transition focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
            >
              {DOMAINS.map((domainOption) => (
                <option key={domainOption} value={domainOption}>
                  {domainOption}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={!asin.trim() || isScraping}
              className="h-11 w-full rounded-md bg-emerald-700 px-5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-zinc-400 lg:w-auto"
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
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "",
              notice.tone === "info" ? "border-sky-200 bg-sky-50 text-sky-800" : "",
              notice.tone === "error" ? "border-red-200 bg-red-50 text-red-800" : "",
            ].join(" ")}
          >
            {notice.message}
          </div>
        ) : null}

        {products.length > 0 ? (
          <section className="flex flex-col gap-5">
            <div className="flex flex-col justify-between gap-4 border-b border-zinc-200 pb-4 sm:flex-row sm:items-end">
              <div>
                <h2 className="text-2xl font-semibold text-zinc-950">Product Scraped</h2>
                <p className="mt-1 text-sm text-zinc-600">
                  Showing {startIndex + 1} - {endIndex} of {products.length} products
                </p>
              </div>

              <label className="flex w-full max-w-36 flex-col gap-2 text-sm font-medium text-zinc-700">
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
                  className="h-10 rounded-md border border-zinc-300 px-3 text-zinc-950 outline-none transition focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
              </label>
            </div>

            <div className="flex flex-col gap-4">
              {visibleProducts.map((product) => (
                <ProductCard
                  key={product.asin}
                  product={product}
                  isSelected={selectedAsin === product.asin}
                  onAnalyze={startCompetitorAnalysis}
                />
              ))}
            </div>
          </section>
        ) : null}

        {selectedAsin ? (
          <section className="flex flex-col gap-5 border-t border-zinc-200 pt-6">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-2xl font-semibold text-zinc-950">
                  Competitor analysis for {selectedAsin}
                </h2>
                <p className="mt-1 text-sm text-zinc-600">
                  {competitors.length > 0
                    ? `${competitors.length} competitors loaded.`
                    : "No competitors loaded yet."}
                </p>
              </div>

              <button
                type="button"
                onClick={refreshCompetitors}
                disabled={isSearchingCompetitors}
                className="h-10 rounded-md border border-zinc-300 bg-white px-4 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:text-zinc-400"
              >
                {isSearchingCompetitors ? "Refreshing..." : "Refresh Competitors"}
              </button>
            </div>

            <div className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm lg:flex-row lg:items-start lg:justify-between">
              <div className="min-h-24 flex-1 rounded-md bg-zinc-50 p-4">
                {analysis ? (
                  <div className="whitespace-pre-wrap text-sm leading-6 text-zinc-800">{analysis}</div>
                ) : (
                  <p className="text-sm text-zinc-500">Analysis output will appear here.</p>
                )}
              </div>

              <button
                type="button"
                onClick={runLlmAnalysis}
                disabled={isAnalyzing}
                className="h-10 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-400"
              >
                {isAnalyzing ? "Running LLM..." : "Analyze with LLM"}
              </button>
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
