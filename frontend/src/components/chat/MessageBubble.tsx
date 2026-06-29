import { AlertTriangle, ShieldAlert, ShieldCheck } from "lucide-react";

import { CitationChip } from "@/components/citations/CitationChip";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types/api";

interface MessageBubbleProps {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  insufficientEvidence?: boolean;
  faithful?: boolean;
  pending?: boolean;
}

export function MessageBubble({
  role,
  text,
  citations = [],
  insufficientEvidence = false,
  faithful = true,
  pending = false,
}: MessageBubbleProps): JSX.Element {
  const isUser = role === "user";

  return (
    <div className={cn("flex animate-slide-up", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "rounded-br-md bg-indigo-600 text-white shadow-sm"
            : "rounded-bl-md border border-slate-200/80 bg-white text-slate-800 shadow-soft",
        )}
      >
        {!isUser && !pending && insufficientEvidence && (
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-600/20">
            <AlertTriangle className="h-3.5 w-3.5" /> Insufficient evidence
          </div>
        )}
        {!isUser && !pending && !insufficientEvidence && !faithful && (
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-md bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700 ring-1 ring-inset ring-rose-600/20">
            <ShieldAlert className="h-3.5 w-3.5" /> Low faithfulness — not verified
          </div>
        )}
        {!isUser && !pending && !insufficientEvidence && faithful && citations.length > 0 && (
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
            <ShieldCheck className="h-3.5 w-3.5" /> Verified · grounded
          </div>
        )}

        <p className="whitespace-pre-wrap">
          {text}
          {pending && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-slate-400 align-middle" />}
        </p>

        {citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5 border-t border-slate-100 pt-2.5">
            {citations.map((c) => (
              <CitationChip key={`${c.marker}-${c.chunk_id}`} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
