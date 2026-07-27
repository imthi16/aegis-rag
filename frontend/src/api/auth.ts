import { apiFetch } from "@/api/client";
import type { TokenResponse, UserMe } from "@/types/api";

export function login(username: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", { method: "POST", body: { username, password } });
}

export function logout(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/auth/logout", { method: "POST", body: {} });
}

export function me(): Promise<UserMe> {
  return apiFetch<UserMe>("/auth/me");
}
