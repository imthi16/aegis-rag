import { apiFetch } from "@/api/client";
import type { EvalRunListResponse } from "@/types/api";

export function listEvalRuns(page = 1, size = 20): Promise<EvalRunListResponse> {
  return apiFetch<EvalRunListResponse>(`/eval/runs?page=${page}&size=${size}`);
}

export function runEval(suite: "ragas" | "deepeval" | "both"): Promise<{ run_id: string }> {
  return apiFetch<{ run_id: string }>("/eval/run", { method: "POST", body: { suite } });
}
