import { useMutation, useQuery } from "@tanstack/react-query";

import { getAiInsights, getAnalysis } from "../services/analysis";

export const analysisKey = (asin: string) => ["analysis", asin] as const;

export function useAnalysis(asin: string | null) {
  return useQuery({
    queryKey: analysisKey(asin ?? ""),
    queryFn: () => getAnalysis(asin!),
    enabled: !!asin,
  });
}

export function useAiInsights() {
  return useMutation({ mutationFn: (asin: string) => getAiInsights(asin) });
}
