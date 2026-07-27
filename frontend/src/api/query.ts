import { apiFetch } from "@/api/client";
import type { QueryResponse } from "@/types/api";

export function runQuery(query: string, topK?: number): Promise<QueryResponse> {
  return apiFetch<QueryResponse>("/query", {
    method: "POST",
    body: topK !== undefined ? { query, top_k: topK } : { query },
  });
}
