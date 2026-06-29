// Shared UI helpers: semantic colour tones for badges/pills.

export type Tone = "indigo" | "emerald" | "amber" | "rose" | "sky" | "slate" | "violet";

export const toneClasses: Record<Tone, string> = {
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  emerald: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  rose: "bg-rose-50 text-rose-700 ring-rose-600/20",
  sky: "bg-sky-50 text-sky-700 ring-sky-600/20",
  slate: "bg-slate-100 text-slate-600 ring-slate-500/20",
  violet: "bg-violet-50 text-violet-700 ring-violet-600/20",
};

export function classificationTone(value: string): Tone {
  switch (value) {
    case "public":
      return "emerald";
    case "internal":
      return "sky";
    case "confidential":
      return "amber";
    case "restricted":
      return "rose";
    default:
      return "slate";
  }
}

export function outcomeTone(value: string): Tone {
  switch (value) {
    case "success":
      return "emerald";
    case "denied":
      return "amber";
    case "error":
      return "rose";
    default:
      return "slate";
  }
}

export function roleTone(value: string): Tone {
  switch (value) {
    case "admin":
      return "violet";
    case "compliance_auditor":
      return "indigo";
    case "analyst":
      return "sky";
    case "viewer":
      return "slate";
    default:
      return "slate";
  }
}

export function initials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}
