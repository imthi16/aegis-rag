import type { QueryResponse } from "@/types/api";

export function EvidencePanel({ response }: { response: QueryResponse }): JSX.Element {
  return (
    <div className="space-y-4 text-sm">
      <section>
        <h3 className="mb-1 font-semibold text-slate-700">Faithfulness</h3>
        <div className="flex items-center gap-2">
          <span
            className={
              response.faithful
                ? "rounded bg-green-100 px-2 py-0.5 text-green-700"
                : "rounded bg-red-100 px-2 py-0.5 text-red-700"
            }
          >
            {response.faithful ? "faithful" : "not faithful"}
          </span>
          <span className="text-slate-500">score {response.faithfulness_score.toFixed(2)}</span>
          {response.correction_applied && (
            <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-700">corrected</span>
          )}
        </div>
      </section>

      <section>
        <h3 className="mb-1 font-semibold text-slate-700">
          Document grades (CRAG) · {response.doc_grades.length}
        </h3>
        <ul className="space-y-1">
          {response.doc_grades.map((g) => (
            <li key={g.chunk_id} className="flex justify-between">
              <span className="text-slate-500">{g.chunk_id.slice(0, 8)}</span>
              <span className={g.relevant ? "text-green-600" : "text-slate-400"}>
                {g.relevant ? "relevant" : "irrelevant"} ({g.score.toFixed(2)})
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="mb-1 font-semibold text-slate-700">
          Retrieved chunks · {response.retrieved_chunks.length}
        </h3>
        <ul className="space-y-2">
          {response.retrieved_chunks.map((c) => (
            <li key={c.chunk_id} className="rounded border border-slate-200 p-2">
              <div className="text-slate-500">
                doc {c.document_id.slice(0, 8)} · page {c.page_number ?? "—"} · score{" "}
                {c.score.toFixed(3)}
              </div>
              <div className="text-slate-700">{c.content_preview}</div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
