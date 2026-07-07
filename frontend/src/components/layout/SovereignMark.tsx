interface SovereignMarkProps {
  className?: string;
}

/** Aegis shield mark; inherits color via `currentColor`. */
export function SovereignMark({ className }: SovereignMarkProps): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M12 2.5 4.5 5.5v6c0 4.6 3.2 8.4 7.5 10 4.3-1.6 7.5-5.4 7.5-10v-6L12 2.5Z" />
      <path d="M8.5 12l2.4 2.4L15.5 9.5" />
    </svg>
  );
}
