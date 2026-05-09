import { requestJson } from "./http";
import { Product, productsFromPayload } from "./types";

export async function getCompetitors(parentAsin: string): Promise<Product[]> {
  const params = new URLSearchParams({ parent_asin: parentAsin });
  const payload = await requestJson<unknown>(`/api/competitors?${params.toString()}`);
  return productsFromPayload(payload);
}

export async function fetchCompetitors(
  asin: string,
  domain: string,
  geoLocation: string,
): Promise<Product[]> {
  const payload = await requestJson<unknown>("/api/competitors/fetch", {
    method: "POST",
    body: JSON.stringify({ asin, domain, geo: geoLocation }),
  });
  return productsFromPayload(payload);
}

export async function refreshCompetitors(
  asin: string,
  domain: string,
  geoLocation: string,
): Promise<Product[]> {
  const payload = await requestJson<unknown>("/api/competitors/refresh", {
    method: "POST",
    body: JSON.stringify({ asin, domain, geo: geoLocation }),
  });
  return productsFromPayload(payload);
}
