import { apiFetch } from "@/api/client";
import type { DocumentListResponse, DocumentSummary } from "@/types/api";

export function listDocuments(page = 1, size = 20): Promise<DocumentListResponse> {
  return apiFetch<DocumentListResponse>(`/documents?page=${page}&size=${size}`);
}

export function uploadDocument(
  file: File,
  classification: string,
  allowedRoles: string[],
): Promise<DocumentSummary> {
  const form = new FormData();
  form.append("file", file);
  form.append("classification", classification);
  for (const role of allowedRoles) form.append("allowed_roles", role);
  return apiFetch<DocumentSummary>("/documents", { method: "POST", body: form, isForm: true });
}

export function deleteDocument(id: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/documents/${id}`, { method: "DELETE" });
}
