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
  const ok = v >= 0.7;
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-fg-faint">
          {label}
        </span>
        <span className="font-mono text-xs tabular-nums text-fg-dim">
          {value === null ? "—" : v.toFixed(2)}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-ink ring-1 ring-inset ring-edge/12">
        <div
          className={cn("h-full rounded-full", ok ? "bg-beacon" : "bg-gold")}
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
        eyebrow="Evaluation"
        title="Faithfulness gate"
        subtitle="RAGAS + local evaluator — run entirely against on-premise models"
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
            <div className="flex items-center gap-2 text-sm text-fg-dim">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading runs…
            </div>
          )}
          {!isLoading && runs.length === 0 && (
            <Card className="grid place-items-center gap-2 p-12 text-center">
              <div className="grid h-12 w-12 place-items-center rounded-md border border-edge/12 bg-ink text-fg-faint">
                <FlaskConical className="h-6 w-6" />
              </div>
              <p className="text-sm font-medium text-fg">No evaluation runs yet</p>
              <p className="text-xs text-fg-faint">
                Trigger a run to gate faithfulness &amp; hallucination.
              </p>
            </Card>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {runs.map((run) => (
              <Card key={run.id} className="p-5">
                <div className="mb-4 flex items-center justify-between">
                  <span className="font-mono text-sm font-semibold uppercase tracking-wider text-fg">
                    {run.suite}
                  </span>
                  <Badge tone={run.passed ? "jade" : "crimson"}>
                    {run.passed ? "passed" : "failed"}
                  </Badge>
                </div>
                <div className="space-y-3.5">
                  <Metric label="Faithfulness" value={run.faithfulness_avg} />
                  <Metric label="Hallucination" value={run.hallucination_rate} />
                </div>
                <div className="mt-4 font-mono text-[10px] text-fg-faint">
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
