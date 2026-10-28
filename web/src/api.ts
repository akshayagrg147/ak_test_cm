import type { Session } from "./types";
let accessToken = "";
let refreshPromise: Promise<Session> | null = null;
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export function setSession(s: Session | null) {
  accessToken = s?.access_token || "";
  window.dispatchEvent(new CustomEvent("crm-session", { detail: s }));
}
export async function refreshSession(): Promise<Session> {
  if (!refreshPromise)
    refreshPromise = fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-With": "TalkoCRM" },
      signal: AbortSignal.timeout(15000),
    })
      .then(async (r) => {
        if (!r.ok) {
          const error = await r.json().catch(() => ({}));
          throw new ApiError(
            error.error?.code || "request_failed",
            error.error?.message ||
              (r.status === 401
                ? "Please sign in again"
                : "Session service unavailable. Try again."),
            r.status,
          );
        }
        const s = (await r.json()) as Session;
        setSession(s);
        return s;
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError) throw error;
        throw new ApiError(
          "network_error",
          "Connection unavailable. Try again.",
          0,
        );
      })
      .finally(() => {
        refreshPromise = null;
      });
  return refreshPromise;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("X-Requested-With", "TalkoCRM");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers,
      credentials: "include",
      signal: options.signal || AbortSignal.timeout(30000),
    });
  } catch {
    throw new ApiError(
      "network_error",
      "Connection unavailable. Check your connection and try again.",
      0,
    );
  }
  if (
    response.status === 401 &&
    retry &&
    (!path.startsWith("/auth/") || path === "/auth/me")
  ) {
    try {
      await refreshSession();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setSession(null);
      throw error;
    }
    return api<T>(path, options, false);
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      error.error?.code || "request_failed",
      error.error?.message || `Request failed (${response.status})`,
      response.status,
    );
  }
  if (response.headers.get("content-type")?.includes("application/json"))
    return response.json() as Promise<T>;
  return response.blob() as Promise<T>;
}
export const send = <T>(path: string, body: unknown, method = "POST") =>
  api<T>(path, { method, body: JSON.stringify(body) });
export function params(
  values: Record<string, string | number | boolean | undefined>,
) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(values))
    if (v !== "" && v !== undefined) p.set(k, String(v));
  return p.toString();
}
export async function download(path: string, name: string) {
  const blob = await api<Blob>(path);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
