// Fetch wrapper (CLAUDE.md §6.18): attaches Bearer; on 401 refreshes once then
// retries; on refresh failure clears the store and routes to /login.

import { useAuthStore } from "@/store/authStore";
import type { ApiErrorBody, RefreshResponse } from "@/types/api";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  requestId: string;
  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.error?.message ?? fallback);
    this.status = status;
    this.code = body?.error?.code ?? "error";
    this.requestId = body?.error?.request_id ?? "";
  }
}

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const { refreshToken, setTokens, logout } = useAuthStore.getState();
  if (!refreshToken) {
    logout();
    return false;
  }
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const resp = await fetch(`${BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!resp.ok) {
          logout();
          return false;
        }
        const data = (await resp.json()) as RefreshResponse;
        setTokens(data.access_token, data.refresh_token);
        return true;
      } catch {
        logout();
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  isForm?: boolean;
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}, retry = true): Promise<T> {
  const { accessToken } = useAuthStore.getState();
  const headers: Record<string, string> = {};
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  let body: BodyInit | undefined;
  if (opts.body !== undefined) {
    if (opts.isForm) {
      body = opts.body as FormData;
    } else {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }
  }

  const init: RequestInit = { method: opts.method ?? "GET", headers };
  if (body !== undefined) {
    init.body = body;
  }
  const resp = await fetch(`${BASE_URL}${path}`, init);

  if (resp.status === 401 && retry) {
    const ok = await tryRefresh();
    if (ok) return apiFetch<T>(path, opts, false);
    if (typeof window !== "undefined") window.location.assign("/login");
  }

  if (!resp.ok) {
    let parsed: ApiErrorBody | null = null;
    try {
      parsed = (await resp.json()) as ApiErrorBody;
    } catch {
      parsed = null;
    }
    throw new ApiError(resp.status, parsed, resp.statusText);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export { BASE_URL };
