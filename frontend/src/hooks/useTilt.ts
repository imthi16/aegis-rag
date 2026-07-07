import { useCallback, useRef } from "react";
import type { PointerEvent, RefObject } from "react";

interface TiltHandlers<T extends HTMLElement> {
  ref: RefObject<T>;
  onPointerMove: (event: PointerEvent<T>) => void;
  onPointerLeave: (event: PointerEvent<T>) => void;
}

/** Pointer-follow tilt effect; `maxDeg` bounds the rotation on each axis. */
export function useTilt<T extends HTMLElement>(maxDeg: number): TiltHandlers<T> {
  const ref = useRef<T>(null);

  const onPointerMove = useCallback(
    (event: PointerEvent<T>) => {
      const el = ref.current;
      if (!el || event.pointerType !== "mouse") return;
      const rect = el.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - 0.5;
      const y = (event.clientY - rect.top) / rect.height - 0.5;
      el.style.transform = `perspective(900px) rotateX(${(-y * maxDeg).toFixed(2)}deg) rotateY(${(x * maxDeg).toFixed(2)}deg)`;
    },
    [maxDeg],
  );

  const onPointerLeave = useCallback((_event: PointerEvent<T>) => {
    const el = ref.current;
    if (el) el.style.transform = "";
  }, []);

  return { ref, onPointerMove, onPointerLeave };
}
