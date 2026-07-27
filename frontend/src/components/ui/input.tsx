import type { InputHTMLAttributes, LabelHTMLAttributes, SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// Fields are milled into the faceplate — recessed wells (shadow-well) so text
// reads as sitting below the surface, lit by the beacon on focus.
const fieldBase =
  "h-10 w-full rounded-md border border-edge/15 bg-ink px-3 text-sm text-fg shadow-well transition-colors placeholder:text-fg-faint focus:border-beacon/60 focus:outline-none focus:ring-1 focus:ring-beacon/40 disabled:opacity-50";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>): JSX.Element {
  return <input className={cn(fieldBase, className)} {...props} />;
}

export function Select({
  className,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>): JSX.Element {
  return <select className={cn(fieldBase, "cursor-pointer", className)} {...props} />;
}

export function Label({
  className,
  ...props
}: LabelHTMLAttributes<HTMLLabelElement>): JSX.Element {
  return (
    <label
      className={cn(
        "mb-1.5 block font-mono text-[11px] uppercase tracking-eyebrow text-fg-faint",
        className,
      )}
      {...props}
    />
  );
}
