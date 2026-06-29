import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Loader2, Play } from "lucide-react";

import { listEvalRuns, runEval } from "@/api/eval";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function Metric({ label, value }: { label: string; value: number | null }): JSX.Element {
  const v = value ?? 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
        <span>{label}</span>
        <span className="font-mono text-slate-600">{value === null ? "—" : v.toFixed(2)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn("h-full rounded-full", v >= 0.7 ? "bg-emerald-500" : "bg-amber-500")}
          style={{ width: `${Math.max(0, Math.min(1, v)) * 100}%` }}
        />
      </div>
    </div>
  );
}

export function EvalPage(): JSX.Element {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["eval-runs"], queryFn: () => listEvalRuns() });
  const trigger = useMutation({
    mutationFn: () => runEval("both"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["eval-runs"] }),
  });

  const runs = data?.items ?? [];

  return (
    <div className="flex h-screen flex-col">
      <PageHeader
        title="Evaluation"
        subtitle="RAGAS + DeepEval against local models only"
        icon={<FlaskConical className="h-5 w-5" />}
        actions={
          <Button onClick={() => trigger.mutate()} disabled={trigger.isPending}>
            {trigger.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run eval
          </Button>
        }
      />
      <div className="scroll-slim flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl">
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading runs…
            </div>
          )}
          {!isLoading && runs.length === 0 && (
            <Card className="grid place-items-center gap-2 p-12 text-center">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-slate-100">
                <FlaskConical className="h-6 w-6 text-slate-400" />
              </div>
              <p className="text-sm font-medium text-slate-600">No evaluation runs yet</p>
              <p className="text-xs text-slate-400">Trigger a run to gate faithfulness & hallucination.</p>
            </Card>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {runs.map((run) => (
              <Card key={run.id} className="p-5">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm font-semibold capitalize text-slate-800">
                    {run.suite}
                  </span>
                  <Badge tone={run.passed ? "emerald" : "rose"}>
                    {run.passed ? "passed" : "failed"}
                  </Badge>
                </div>
                <div className="space-y-3">
                  <Metric label="Faithfulness" value={run.faithfulness_avg} />
                  <Metric label="Hallucination" value={run.hallucination_rate} />
                </div>
                <div className="mt-4 text-[11px] text-slate-400">
                  {new Date(run.created_at).toLocaleString()}
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
