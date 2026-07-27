import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Loader2, Play } from "lucide-react";

import { listEvalRuns, runEval } from "@/api/eval";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { Tone } from "@/lib/ui";
import { cn } from "@/lib/utils";
import type { EvalRunSummary } from "@/types/api";

// Mirrors FAITHFULNESS_THRESHOLD and the ci_gate rule: a run passes when
// faithfulness >= 0.7 and hallucination <= 1 - 0.7. The two metrics are read in
// opposite directions, so each carries its own gate rather than sharing one.
const FAITHFULNESS_GATE = 0.7;
const HALLUCINATION_GATE = 1 - FAITHFULNESS_GATE;

const POLL_MS = 4000;

interface Verdict {
  label: string;
  tone: Tone;
  note: string;
}

// A run has three outcomes the operator has to tell apart: still working, done
// and judged, or crashed. Crimson is reserved for "the model missed the trust
// bar" (as in the evidence panel); a suite that never finished is an
// operational fault, not a quality verdict, so it reads gold.
function verdictOf(run: EvalRunSummary): Verdict {
  if (run.status === "running") {
    return { label: "Running", tone: "beacon", note: "Grading against on-premise models." };
  }
  if (run.status === "failed") {
    return {
      label: "Errored",
      tone: "gold",
      note: "The suite stopped before it finished. Check the backend log, then run again.",
    };
  }
  return run.passed
    ? { label: "Passed", tone: "jade", note: "Cleared the faithfulness gate." }
    : {
        label: "Below gate",
        tone: "crimson",
        note: "Faithfulness under the gate, or hallucination over it.",
      };
}

function Metric({
  label,
  value,
  gate,
  lowerIsBetter = false,
  pending = false,
}: {
  label: string;
  value: number | null;
  gate: number;
  lowerIsBetter?: boolean;
  pending?: boolean;
}): JSX.Element {
  const known = !pending && value !== null;
  const v = value ?? 0;
  const ok = lowerIsBetter ? v <= gate : v >= gate;

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-eyebrow text-fg-faint">
          {label}
        </span>
        <span className="font-mono text-xs tabular-nums text-fg-dim">
          {known ? v.toFixed(2) : "—"}
          <span className="ml-1 text-fg-faint">
            {lowerIsBetter ? "≤" : "≥"}
            {gate.toFixed(2)}
          </span>
        </span>
      </div>
      <div className="relative h-1.5 overflow-hidden rounded-full bg-ink ring-1 ring-inset ring-edge/12">
        {known ? (
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-700 ease-out",
              ok ? "bg-beacon" : "bg-crimson",
            )}
            style={{ width: `${Math.max(0, Math.min(1, v)) * 100}%` }}
          />
        ) : (
          // Indeterminate: no score exists yet. Full width at low opacity, so
          // it reads as an energized track rather than a fill level — a partial
          // bar would look like a real score once reduced motion stills it.
          <div className="h-full w-full animate-pulse-dot rounded-full bg-beacon/20" />
        )}
      </div>
    </div>
  );
}

function RunCard({ run }: { run: EvalRunSummary }): JSX.Element {
  const verdict = verdictOf(run);
  const running = run.status === "running";

  return (
    <Card className={cn("p-5", running && "ring-1 ring-inset ring-beacon/20")}>
      <div className="mb-4 flex items-center justify-between gap-2">
        <span className="font-mono text-sm font-semibold uppercase tracking-wider text-fg">
          {run.suite}
        </span>
        <Badge tone={verdict.tone}>
          {running && (
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-pulse-dot rounded-full bg-beacon" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-beacon" />
            </span>
          )}
          {verdict.label}
        </Badge>
      </div>

      <div className="space-y-3.5">
        <Metric
          label="Faithfulness"
          value={run.faithfulness_avg}
          gate={FAITHFULNESS_GATE}
          pending={running}
        />
        <Metric
          label="Hallucination"
          value={run.hallucination_rate}
          gate={HALLUCINATION_GATE}
          lowerIsBetter
          pending={running}
        />
      </div>

      <p className="mt-4 text-xs leading-snug text-fg-faint">{verdict.note}</p>
      <div className="mt-2 font-mono text-[10px] text-fg-faint">
        {new Date(run.created_at).toLocaleString()}
      </div>
    </Card>
  );
}

export function EvalPage(): JSX.Element {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["eval-runs"],
    queryFn: () => listEvalRuns(),
    // A run is graded in the background and takes minutes. Poll only while one
    // is actually in flight, then fall still.
    refetchInterval: (query) =>
      (query.state.data?.items ?? []).some((r) => r.status === "running") ? POLL_MS : false,
  });

  const trigger = useMutation({
    mutationFn: () => runEval("both"),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["eval-runs"] }),
  });

  const runs = data?.items ?? [];
  const runningCount = runs.filter((r) => r.status === "running").length;

  return (
    <div className="flex h-screen flex-col">
      <PageHeader
        eyebrow="Evaluation"
        title="Faithfulness gate"
        subtitle="RAGAS + local evaluator — run entirely against on-premise models"
        icon={<FlaskConical className="h-5 w-5" />}
        actions={
          <div className="flex items-center gap-3">
            {runningCount > 0 && (
              <span className="font-mono text-[10px] uppercase tracking-eyebrow text-beacon">
                {runningCount} running
              </span>
            )}
            <Button onClick={() => trigger.mutate()} disabled={trigger.isPending}>
              {trigger.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run eval
            </Button>
          </div>
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
              <p className="max-w-xs text-xs leading-relaxed text-fg-faint">
                Run the suite to grade the pipeline for faithfulness and hallucination. Scoring
                happens in the background and takes a few minutes.
              </p>
            </Card>
          )}

          {trigger.isError && (
            <div className="mb-4 rounded-md bg-crimson/10 px-3 py-2 text-sm text-crimson ring-1 ring-inset ring-crimson/25">
              Could not start the run: {(trigger.error as Error).message}
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {runs.map((run) => (
              <RunCard key={run.id} run={run} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
