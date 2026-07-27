import { useRef } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

interface Tilt<T extends HTMLElement> {
  ref: React.RefObject<T>;
  onPointerMove: (e: ReactPointerEvent<T>) => void;
  onPointerLeave: () => void;
}

const prefersReduced = (): boolean =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Leans a surface toward the pointer and moves a specular highlight with it.
// Writes CSS custom properties straight to the node (no React state → no
// re-render on every move), and stays flat when reduced motion is requested.
export function useTilt<T extends HTMLElement = HTMLDivElement>(max = 6): Tilt<T> {
  const ref = useRef<T>(null);

  const onPointerMove = (e: ReactPointerEvent<T>): void => {
    const el = ref.current;
    if (!el || prefersReduced()) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    el.style.setProperty("--ry", `${(px - 0.5) * 2 * max}deg`);
    el.style.setProperty("--rx", `${-(py - 0.5) * 2 * max}deg`);
    el.style.setProperty("--mx", `${px * 100}%`);
    el.style.setProperty("--my", `${py * 100}%`);
  };

  const onPointerLeave = (): void => {
    const el = ref.current;
    if (!el) return;
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
  };

  return { ref, onPointerMove, onPointerLeave };
}
