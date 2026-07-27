import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";
import { type Tone, toneClasses } from "@/lib/ui";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

// A classification stamp: mono, uppercase, hairline-ringed. Reads as a label
// applied to the data, not a decorative pill.
export function Badge({ tone = "slate", className, ...props }: BadgeProps): JSX.Element {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10.5px] font-medium uppercase tracking-wider ring-1 ring-inset",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}
