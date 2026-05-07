import { useMutation } from "@tanstack/react-query";

import { analyzeCompetitors } from "../lib/api";

export function useAnalyzeCompetitors() {
  return useMutation({ mutationFn: analyzeCompetitors });
}
