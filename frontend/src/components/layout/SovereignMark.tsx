interface MarkProps {
  className?: string;
  title?: string;
}

// The Aegis seal: a hexagonal sovereign stamp with a chain link at its core —
// the two motifs the platform is built on (a sealed perimeter, a tamper-evident
// chain). Drawn in currentColor so it inherits the beacon.
export function SovereignMark({ className, title = "Aegis" }: MarkProps): JSX.Element {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label={title}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Outer seal */}
      <path
        d="M16 2.5 27.5 9v14L16 29.5 4.5 23V9L16 2.5Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        opacity="0.55"
      />
      {/* Inner seal */}
      <path
        d="M16 7 23 11v10l-7 4-7-4V11l7-4Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
        opacity="0.9"
      />
      {/* Chain link at the core */}
      <rect
        x="12.4"
        y="13.6"
        width="4.2"
        height="6.6"
        rx="2.1"
        transform="rotate(-32 14.5 16.9)"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <rect
        x="15.4"
        y="11.8"
        width="4.2"
        height="6.6"
        rx="2.1"
        transform="rotate(-32 17.5 15.1)"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
}
