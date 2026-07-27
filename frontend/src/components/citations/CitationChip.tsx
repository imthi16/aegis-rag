import { useState } from "react";

import { fingerprint } from "@/lib/ui";
import type { Citation } from "@/types/api";

export function CitationChip({ citation }: { citation: Citation }): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center rounded-sm bg-beacon/10 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-beacon ring-1 ring-inset ring-beacon/25 transition-colors hover:bg-beacon/20"
      >
        [{citation.marker}]
      </button>
      {open && (
        <div className="absolute bottom-full left-0 z-20 mb-2 w-80 animate-fade-in rounded-md border border-edge/15 bg-slab p-3 shadow-lift">
          <div className="mb-2 flex items-center justify-between border-b border-edge/12 pb-1.5 font-mono text-[10px] uppercase tracking-wider text-fg-faint">
            <span>doc {fingerprint(citation.document_id, 8, 0)}</span>
            <span>
              p{citation.page_number ?? "—"} · {citation.char_start}–{citation.char_end}
            </span>
          </div>
          <p className="text-xs leading-relaxed text-fg-dim">{citation.snippet}</p>
        </div>
      )}
    </span>
  );
}
