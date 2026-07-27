// Shared UI helpers. Color is earned: a tone is assigned only where it encodes
// meaning (classification level, action outcome, role, trust). On the ink
// surface each tone is a low-opacity wash + a solid label + a hairline ring.

export type Tone = "beacon" | "jade" | "azure" | "gold" | "crimson" | "violet" | "slate";

export const toneClasses: Record<Tone, string> = {
  beacon: "bg-beacon/10 text-beacon ring-beacon/30",
  jade: "bg-jade/10 text-jade ring-jade/30",
  azure: "bg-azure/10 text-azure ring-azure/30",
  gold: "bg-gold/10 text-gold ring-gold/30",
  crimson: "bg-crimson/10 text-crimson ring-crimson/30",
  violet: "bg-violet-400/10 text-violet-300 ring-violet-400/30",
  slate: "bg-edge/10 text-fg-dim ring-edge/20",
};

// Classification is a ramp of exposure: open → sealed.
export function classificationTone(value: string): Tone {
  switch (value) {
    case "public":
      return "jade";
    case "internal":
      return "azure";
    case "confidential":
      return "gold";
    case "restricted":
      return "crimson";
    default:
      return "slate";
  }
}

export function outcomeTone(value: string): Tone {
  switch (value) {
    case "success":
      return "jade";
    case "denied":
      return "gold";
    case "error":
      return "crimson";
    default:
      return "slate";
  }
}

export function roleTone(value: string): Tone {
  switch (value) {
    case "admin":
      return "violet";
    case "compliance_auditor":
      return "beacon";
    case "analyst":
      return "azure";
    case "viewer":
      return "slate";
    default:
      return "slate";
  }
}

export function initials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

// A short, monospace hash fingerprint — first + last groups, like a git shortref.
export function fingerprint(hash: string, head = 6, tail = 4): string {
  if (!hash || hash.length <= head + tail + 1) return hash;
  // `slice(-0)` is `slice(0)` — the WHOLE string. Callers that want a head-only
  // ref pass tail = 0 (CitationChip, EvidencePanel, AuditTable resource ids),
  // which otherwise rendered "a3f91c04…" followed by the entire untruncated id.
  if (tail <= 0) return `${hash.slice(0, head)}…`;
  return `${hash.slice(0, head)}…${hash.slice(-tail)}`;
}
