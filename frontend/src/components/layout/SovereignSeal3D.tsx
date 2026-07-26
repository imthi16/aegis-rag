import { cn } from "@/lib/utils";

interface SealProps {
  className?: string;
}

// The Aegis seal, built as real geometry: concentric hexagonal plates stacked
// along the Z-axis with the chain link standing proud at the front. The whole
// assembly sways through a 3/4 arc, so the depth between plates parallaxes and
// the engraved beacon lines catch the light. Pure CSS 3D — no dependencies.
export function SovereignSeal3D({ className }: SealProps): JSX.Element {
  return (
    <div
      className={cn("relative", className)}
      style={{ perspective: "560px" }}
      role="img"
      aria-label="Aegis sovereign seal"
    >
      {/* Cast contact shadow on the surface below. */}
      <div className="absolute left-1/2 top-[70%] h-6 w-4/5 -translate-x-1/2 rounded-[50%] bg-black/70 blur-lg" />
      {/* Ambient beacon halo behind the medallion. */}
      <div className="absolute inset-[-18%] rounded-full bg-beacon/10 blur-2xl" />

      <div className="flat-3d absolute inset-0 animate-seal-sway">
        {/* Base plate — the mass of the coin, set deepest. */}
        <div
          className="hex absolute inset-0"
          style={{
            transform: "translateZ(-16px)",
            background: "linear-gradient(160deg, #1a2b3f 0%, #0a1019 72%)",
          }}
        />
        {/* Raised bezel ring. */}
        <div
          className="hex absolute inset-[7%]"
          style={{
            transform: "translateZ(-4px)",
            background: "linear-gradient(150deg, #2c4258 0%, #111c29 58%, #0b1420 100%)",
          }}
        />
        {/* Recessed inner field where the mark is engraved. */}
        <div
          className="hex absolute inset-[20%]"
          style={{
            transform: "translateZ(4px)",
            background: "linear-gradient(160deg, #0f1a29 0%, #070c13 100%)",
          }}
        />

        {/* Engraved seal lines — crisp beacon strokes floating above the field. */}
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          fill="none"
          style={{ transform: "translateZ(8px)" }}
        >
          <polygon
            points="50,3 95,26.5 95,73.5 50,97 5,73.5 5,26.5"
            stroke="#39D6C4"
            strokeOpacity="0.55"
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
          <polygon
            points="50,15 82,32 82,68 50,85 18,68 18,32"
            stroke="#39D6C4"
            strokeOpacity="0.85"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>

        {/* Chain link at the core — the closest, brightest element. */}
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          fill="none"
          style={{
            transform: "translateZ(20px)",
            filter: "drop-shadow(0 3px 6px rgba(0,0,0,0.6)) drop-shadow(0 0 8px rgba(57,214,196,0.5))",
          }}
        >
          <rect
            x="37"
            y="43"
            width="14"
            height="23"
            rx="7"
            transform="rotate(-32 44 54.5)"
            stroke="#8FF3E9"
            strokeWidth="3.4"
          />
          <rect
            x="49"
            y="34"
            width="14"
            height="23"
            rx="7"
            transform="rotate(-32 56 45.5)"
            stroke="#39D6C4"
            strokeWidth="3.4"
          />
        </svg>
      </div>
    </div>
  );
}
