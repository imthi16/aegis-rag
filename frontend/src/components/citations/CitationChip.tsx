import { useState } from "react";

import type { Citation } from "@/types/api";

export function CitationChip({ citation }: { citation: Citation }): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="mr-1 rounded bg-slate-200 px-1.5 py-0.5 text-xs font-medium text-slate-700 hover:bg-slate-300"
      >
        [{citation.marker}]
      </button>
      {open && (
        <div className="absolute z-10 mt-1 w-72 rounded border border-slate-300 bg-white p-2 text-xs shadow-lg">
          <div className="mb-1 font-semibold text-slate-600">
            doc {citation.document_id.slice(0, 8)} · page {citation.page_number ?? "—"} · chars{" "}
            {citation.char_start}–{citation.char_end}
          </div>
          <div className="text-slate-700">{citation.snippet}</div>
        </div>
      )}
    </span>
  );
}
