import { useMutation } from "@tanstack/react-query";

import { analyzeCompetitors } from "../services";

export function useAnalyzeCompetitors() {
  return useMutation({ mutationFn: analyzeCompetitors });
}
