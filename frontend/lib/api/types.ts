import { isRecord, stringValue } from "./http";

export type Product = {
  asin: string;
  parent_asin?: string;
  title?: string;
  images?: string[];
  currency?: string;
  price?: number | string;
  rating?: number | string;
  brand?: string;
  product?: string;
  amazon_domain?: string;
  geo_location?: string;
  url?: string;
};

export function normalizeProduct(value: unknown): Product | null {
  if (!isRecord(value)) return null;
  const asin = stringValue(value.asin);
  if (!asin) return null;
  return {
    asin,
    parent_asin: stringValue(value.parent_asin),
    title: stringValue(value.title),
    images: Array.isArray(value.images)
      ? value.images.filter((img): img is string => typeof img === "string")
      : [],
    currency: stringValue(value.currency),
    price:
      typeof value.price === "number" || typeof value.price === "string"
        ? value.price
        : undefined,
    rating:
      typeof value.rating === "number" || typeof value.rating === "string"
        ? value.rating
        : undefined,
    brand: stringValue(value.brand),
    product: stringValue(value.product),
    amazon_domain: stringValue(value.amazon_domain),
    geo_location: stringValue(value.geo_location),
    url: stringValue(value.url),
  };
}

export function mergeProducts(existing: Product[], incoming: Product[]): Product[] {
  const map = new Map(existing.map((p) => [p.asin, p]));
  for (const p of incoming) map.set(p.asin, { ...map.get(p.asin), ...p });
  return Array.from(map.values());
}

export function productsFromPayload(payload: unknown): Product[] {
  if (Array.isArray(payload)) {
    return payload.map(normalizeProduct).filter((p): p is Product => p !== null);
  }
  if (!isRecord(payload)) return [];
  for (const key of ["products", "competitors", "items", "results"]) {
    const value = payload[key];
    if (Array.isArray(value)) {
      return value.map(normalizeProduct).filter((p): p is Product => p !== null);
    }
  }
  const product = normalizeProduct(payload.product) ?? normalizeProduct(payload);
  return product ? [product] : [];
}
