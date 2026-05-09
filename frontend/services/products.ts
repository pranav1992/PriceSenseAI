import { requestJson } from "./http";
import { Product, productsFromPayload } from "./types";

export async function getProducts(): Promise<Product[]> {
  const payload = await requestJson<unknown>("/api/products");
  return productsFromPayload(payload);
}

export async function scrapeProduct(asin: string, geoLocation: string, domain: string): Promise<Product[]> {
  const payload = await requestJson<unknown>("/api/products/scrape", {
    method: "POST",
    body: JSON.stringify({ asin, geo_location: geoLocation, domain }),
  });
  return productsFromPayload(payload);
}
