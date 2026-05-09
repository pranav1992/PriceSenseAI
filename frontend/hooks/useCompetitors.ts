import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchCompetitors, getCompetitors } from "../services";
import type { Product } from "../services";

export const competitorsKey = (asin: string) => ["competitors", asin] as const;

export function useCompetitorsQuery(asin: string | null) {
  return useQuery({
    queryKey: competitorsKey(asin ?? ""),
    queryFn: () => getCompetitors(asin!),
    enabled: !!asin,
  });
}

export function useStartCompetitorAnalysis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      asin,
      domain,
      geoLocation,
    }: {
      asin: string;
      domain: string;
      geoLocation: string;
    }) => {
      // const existing = await getCompetitors(asin);
      // if (existing.length > 0) return { competitors: existing, fromCache: true };
      const fetched = await fetchCompetitors(asin, domain, geoLocation);
      return { competitors: fetched, fromCache: false };
    },
    onSuccess: ({ competitors }, { asin }) => {
      queryClient.setQueryData<Product[]>(competitorsKey(asin), competitors);
    },
  });
}

export function useRefreshCompetitors() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      asin,
      domain,
      geoLocation,
    }: {
      asin: string;
      domain: string;
      geoLocation: string;
    }) => fetchCompetitors(asin, domain, geoLocation),
    onSuccess: (competitors, { asin }) => {
      queryClient.setQueryData<Product[]>(competitorsKey(asin), competitors);
    },
  });
}
