import { AlertTriangle, ShieldAlert, ShieldCheck } from "lucide-react";

import { CitationChip } from "@/components/citations/CitationChip";
import { useTilt } from "@/hooks/useTilt";
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

type Trust = {
  label: string;
  icon: typeof ShieldCheck;
  accent: string; // left rail
  chip: string; // stamp classes
};

function trustState(insufficient: boolean, faithful: boolean): Trust {
  if (insufficient)
    return {
      label: "Insufficient evidence",
      icon: AlertTriangle,
      accent: "bg-gold",
      chip: "bg-gold/10 text-gold ring-gold/30",
    };
  if (!faithful)
    return {
      label: "Unverified · low faithfulness",
      icon: ShieldAlert,
      accent: "bg-crimson",
      chip: "bg-crimson/10 text-crimson ring-crimson/30",
    };
  return {
    label: "Verified · grounded",
    icon: ShieldCheck,
    accent: "bg-beacon",
    chip: "bg-beacon/10 text-beacon ring-beacon/30",
  };
}

export function MessageBubble({
  role,
  text,
  citations = [],
  insufficientEvidence = false,
  faithful = true,
  pending = false,
}: MessageBubbleProps): JSX.Element {
  // Declared before the user-role branch below: hooks must run in the same
  // order on every render, so this cannot sit after an early return.
  const tilt = useTilt<HTMLDivElement>(4.5);

  if (role === "user") {
    return (
      <div className="flex animate-slide-up justify-end">
        <div className="max-w-[80%] rounded-md rounded-br-sm bg-raise px-4 py-2.5 text-sm leading-relaxed text-fg ring-1 ring-inset ring-edge/12">
          {text}
        </div>
      </div>
    );
  }

  const trust = !pending ? trustState(insufficientEvidence, faithful) : null;
  const Icon = trust?.icon;

  return (
    <div className="flex animate-slide-up justify-start">
      <div
        ref={tilt.ref}
        onPointerMove={tilt.onPointerMove}
        onPointerLeave={tilt.onPointerLeave}
        className="hw spec tilt-card relative w-full max-w-[88%] overflow-hidden rounded-lg"
      >
        {/* Trust rail — the answer's grounding, encoded as color. */}
        <span
          className={cn(
            "absolute inset-y-0 left-0 w-[3px]",
            pending ? "bg-edge/25" : trust?.accent,
          )}
        />
        <div className="flat-3d px-4 py-3.5 pl-5">
          {trust && Icon && (
            <div
              style={{ transform: "translateZ(22px)" }}
              className={cn(
                "mb-2.5 inline-flex items-center gap-1.5 rounded px-2 py-1 font-mono text-[10.5px] font-medium uppercase tracking-wider shadow-e1 ring-1 ring-inset",
                trust.chip,
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {trust.label}
            </div>
          )}

          <p className="whitespace-pre-wrap text-sm leading-relaxed text-fg">
            {text}
            {pending && (
              <span className="ml-0.5 inline-block h-4 w-[7px] animate-caret bg-beacon align-middle" />
            )}
          </p>

          {citations.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-edge/12 pt-3">
              <span className="mr-0.5 font-mono text-[10px] uppercase tracking-eyebrow text-fg-faint">
                sources
              </span>
              {citations.map((c) => (
                <CitationChip key={`${c.marker}-${c.chunk_id}`} citation={c} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
