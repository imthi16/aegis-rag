import { CheckCircle2, CircleSlash, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { QueryResponse } from "@/types/api";

function ScoreBar({ value, tone }: { value: number; tone: string }): JSX.Element {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
      <div
        className={cn("h-full rounded-full", tone)}
        style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
      />
    </div>
  );
}

export function EvidencePanel({ response }: { response: QueryResponse }): JSX.Element {
  const faithTone = response.faithful ? "bg-emerald-500" : "bg-rose-500";
  return (
    <div className="space-y-5 text-sm">
      <section>
        <div className="mb-2 flex items-center justify-between">
          <span className="font-semibold text-slate-700">Faithfulness</span>
          <Badge tone={response.faithful ? "emerald" : "rose"}>
            {response.faithful ? "faithful" : "unverified"}
          </Badge>
        </div>
        <ScoreBar value={response.faithfulness_score} tone={faithTone} />
        <div className="mt-1.5 flex items-center justify-between text-xs text-slate-500">
          <span>score {response.faithfulness_score.toFixed(2)}</span>
          {response.correction_applied && <Badge tone="amber">CRAG corrected</Badge>}
        </div>
      </section>

      <section>
        <div className="mb-2 flex items-center gap-1.5 font-semibold text-slate-700">
          <Sparkles className="h-4 w-4 text-indigo-500" /> Document grades
          <span className="text-xs font-normal text-slate-400">({response.doc_grades.length})</span>
        </div>
        <ul className="space-y-1.5">
          {response.doc_grades.map((g) => (
            <li
              key={g.chunk_id}
              className="flex items-center justify-between rounded-lg bg-slate-50 px-2.5 py-1.5"
            >
              <span className="flex items-center gap-1.5 text-xs text-slate-500">
                {g.relevant ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                ) : (
                  <CircleSlash className="h-3.5 w-3.5 text-slate-400" />
                )}
                {g.chunk_id.slice(0, 8)}
              </span>
              <span className="font-mono text-xs text-slate-600">{g.score.toFixed(2)}</span>
            </li>
          ))}
          {response.doc_grades.length === 0 && (
            <li className="text-xs text-slate-400">No grades.</li>
          )}
        </ul>
      </section>

      <section>
        <div className="mb-2 font-semibold text-slate-700">
          Retrieved chunks
          <span className="ml-1 text-xs font-normal text-slate-400">
            ({response.retrieved_chunks.length})
          </span>
        </div>
        <ul className="space-y-2">
          {response.retrieved_chunks.map((c) => (
            <li key={c.chunk_id} className="rounded-xl border border-slate-200/70 bg-white p-2.5">
              <div className="mb-1 flex items-center justify-between text-[11px] text-slate-400">
                <span>doc {c.document_id.slice(0, 8)} · page {c.page_number ?? "—"}</span>
                <span className="font-mono">{c.score.toFixed(3)}</span>
              </div>
              <p className="line-clamp-3 text-xs leading-relaxed text-slate-600">
                {c.content_preview}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
