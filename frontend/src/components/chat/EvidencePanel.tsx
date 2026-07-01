import { Check, Minus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { fingerprint } from "@/lib/ui";
import type { QueryResponse } from "@/types/api";

const FAITH_THRESHOLD = 0.7;

// A faithfulness gauge: a filled meter with a fixed threshold tick, so the
// score is read against the bar the system actually gates on.
function Gauge({ value, ok }: { value: number; ok: boolean }): JSX.Element {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-ink shadow-well">
      <div
        className={cn("h-full rounded-full transition-[width] duration-700 ease-out", ok ? "bg-beacon" : "bg-crimson")}
        style={{ width: `${pct}%` }}
      />
      <div
        className="absolute inset-y-0 w-px bg-fg/40"
        style={{ left: `${FAITH_THRESHOLD * 100}%` }}
        title={`threshold ${FAITH_THRESHOLD}`}
      />
    </div>
  );
}

function Section({
  label,
  count,
  children,
}: {
  label: string;
  count?: number;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section>
      <div className="mb-2.5 flex items-baseline justify-between">
        <span className="eyebrow">{label}</span>
        {count !== undefined && <span className="font-mono text-[11px] text-fg-faint">{count}</span>}
      </div>
      {children}
    </section>
  );
}

export function EvidencePanel({ response }: { response: QueryResponse }): JSX.Element {
  const ok = response.faithful;
  return (
    <div className="space-y-6">
      <Section label="Faithfulness">
        <div className="well p-3.5">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="font-mono text-2xl font-semibold tabular-nums text-fg">
              {response.faithfulness_score.toFixed(2)}
            </span>
            <Badge tone={ok ? "beacon" : "crimson"}>{ok ? "verified" : "unverified"}</Badge>
          </div>
          <Gauge value={response.faithfulness_score} ok={ok} />
          <div className="mt-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-fg-faint">
            <span>gate ≥ {FAITH_THRESHOLD.toFixed(2)}</span>
            {response.correction_applied && <span className="text-gold">CRAG corrected</span>}
          </div>
        </div>
      </Section>

      <Section label="Document grades" count={response.doc_grades.length}>
        <ul className="space-y-1">
          {response.doc_grades.map((g) => (
            <li
              key={g.chunk_id}
              className="flex items-center justify-between rounded-md border border-edge/10 bg-ink/40 px-2.5 py-1.5"
            >
              <span className="flex items-center gap-2">
                <span
                  className={cn(
                    "grid h-4 w-4 place-items-center rounded-sm",
                    g.relevant ? "bg-jade/15 text-jade" : "bg-edge/10 text-fg-faint",
                  )}
                >
                  {g.relevant ? <Check className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                </span>
                <span className="hash">{fingerprint(g.chunk_id, 8, 0)}</span>
              </span>
              <span className="font-mono text-xs tabular-nums text-fg-dim">
                {g.score.toFixed(2)}
              </span>
            </li>
          ))}
          {response.doc_grades.length === 0 && (
            <li className="text-xs text-fg-faint">No grades.</li>
          )}
        </ul>
      </Section>

      <Section label="Retrieved spans" count={response.retrieved_chunks.length}>
        <ul className="space-y-2">
          {response.retrieved_chunks.map((c) => (
            <li key={c.chunk_id} className="rounded-md border border-edge/12 bg-ink/40 p-2.5">
              <div className="mb-1.5 flex items-center justify-between font-mono text-[10px] text-fg-faint">
                <span>
                  doc {fingerprint(c.document_id, 8, 0)} · p{c.page_number ?? "—"}
                </span>
                <span className="tabular-nums text-fg-dim">{c.score.toFixed(3)}</span>
              </div>
              <p className="line-clamp-3 text-xs leading-relaxed text-fg-dim">{c.content_preview}</p>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
