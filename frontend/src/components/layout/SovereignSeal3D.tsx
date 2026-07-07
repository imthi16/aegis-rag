import { SovereignMark } from "@/components/layout/SovereignMark";

interface SovereignSeal3DProps {
  className?: string;
}

/** Raised circular seal around the shield mark, used on the login screen. */
export function SovereignSeal3D({ className }: SovereignSeal3DProps): JSX.Element {
  return (
    <div
      className={`relative flex items-center justify-center rounded-full border border-edge/25 bg-slab shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_14px_30px_-16px_rgba(0,0,0,0.9)] ${className ?? ""}`}
      aria-hidden="true"
    >
      <div className="absolute inset-1.5 rounded-full border border-edge/15" />
      <SovereignMark className="h-1/2 w-1/2 text-beacon" />
    </div>
  );
}
