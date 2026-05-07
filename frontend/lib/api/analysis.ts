import { isRecord, requestJson, stringValue } from "./http";

export async function analyzeCompetitors(asin: string): Promise<string> {
  const payload = await requestJson<unknown>("/api/analysis/competitors", {
    method: "POST",
    body: JSON.stringify({ asin }),
  });
  if (typeof payload === "string") return payload;
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
