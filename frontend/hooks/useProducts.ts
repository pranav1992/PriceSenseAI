import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getProducts, mergeProducts, scrapeProduct } from "../lib/api";
import type { Product } from "../lib/api";

export const PRODUCTS_KEY = ["products"] as const;

export function useProductsQuery() {
  return useQuery({ queryKey: PRODUCTS_KEY, queryFn: getProducts });
}

export function useScrapeProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ asin, geoLocation }: { asin: string; geoLocation: string }) =>
      scrapeProduct(asin, geoLocation),
    onSuccess: (incoming) => {
      queryClient.setQueryData<Product[]>(PRODUCTS_KEY, (current = []) =>
        incoming.length > 0 ? mergeProducts(current, incoming) : current,
      );
      if (incoming.length === 0) {
        void queryClient.invalidateQueries({ queryKey: PRODUCTS_KEY });
      }
    },
  });
}
