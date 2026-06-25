import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listEvalRuns, runEval } from "@/api/eval";

export function EvalPage(): JSX.Element {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["eval-runs"], queryFn: () => listEvalRuns() });
  const trigger = useMutation({
    mutationFn: () => runEval("both"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["eval-runs"] }),
  });

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Evaluation</h1>
        <button
          type="button"
          onClick={() => trigger.mutate()}
          disabled={trigger.isPending}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {trigger.isPending ? "Running…" : "Run eval (both)"}
        </button>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {(data?.items ?? []).map((run) => (
          <div key={run.id} className="rounded border border-slate-200 bg-white p-3 text-sm">
            <div className="mb-1 flex items-center justify-between">
              <span className="font-semibold text-slate-700">{run.suite}</span>
              <span
                className={
                  run.passed
                    ? "rounded bg-green-100 px-2 py-0.5 text-green-700"
                    : "rounded bg-red-100 px-2 py-0.5 text-red-700"
                }
              >
                {run.passed ? "passed" : "failed"}
              </span>
            </div>
            <div className="text-slate-500">
              faithfulness {run.faithfulness_avg ?? "—"} · hallucination{" "}
              {run.hallucination_rate ?? "—"}
            </div>
            <div className="text-xs text-slate-400">{new Date(run.created_at).toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
