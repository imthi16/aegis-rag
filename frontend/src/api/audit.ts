import { apiFetch } from "@/api/client";
import type { AuditListResponse, ChainReport } from "@/types/api";

export function listAudit(page = 1, size = 50): Promise<AuditListResponse> {
  return apiFetch<AuditListResponse>(`/audit?page=${page}&size=${size}`);
}

export function verifyChain(): Promise<ChainReport> {
  return apiFetch<ChainReport>("/audit/verify");
}
