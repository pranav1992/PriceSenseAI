const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function readErrorMessage(text: string, status: number, path: string): string {
  if (text) {
    try {
      const payload = JSON.parse(text) as unknown;
      if (isRecord(payload)) {
        if (isRecord(payload.error)) {
          const msg = stringValue(payload.error.message);
          if (msg) return msg;
        }
        const detail =
          stringValue(payload.detail) ??
          stringValue(payload.message) ??
          stringValue(payload.error as unknown);
        if (detail) return detail;
      }
    } catch {
      if (!text.trim().startsWith("<") && text.length < 180) return text;
    }
  }
  return `Request to ${path} failed with status ${status}.`;
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
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
  if (!text) return null as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}
