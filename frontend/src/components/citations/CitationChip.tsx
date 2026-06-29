import { FileText } from "lucide-react";
import { useState } from "react";

import type { Citation } from "@/types/api";

export function CitationChip({ citation }: { citation: Citation }): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-1.5 py-0.5 text-xs font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-600/20 transition-colors hover:bg-indigo-100"
      >
        <FileText className="h-3 w-3" />[{citation.marker}]
      </button>
      {open && (
        <div className="absolute bottom-full left-0 z-20 mb-2 w-80 animate-fade-in rounded-xl border border-slate-200 bg-white p-3 text-xs shadow-glow">
          <div className="mb-1.5 flex items-center justify-between font-medium text-slate-500">
            <span>doc {citation.document_id.slice(0, 8)}</span>
            <span>
              page {citation.page_number ?? "—"} · {citation.char_start}–{citation.char_end}
            </span>
          </div>
          <p className="leading-relaxed text-slate-700">{citation.snippet}</p>
        </div>
      )}
    </span>
  );
}
