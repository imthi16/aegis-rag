import { LoginForm } from "@/components/auth/LoginForm";

export function LoginPage(): JSX.Element {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-ink p-4">
      {/* Instrument backdrop, built in depth planes: a receding grid, a beacon
          beam, and a vignette that sinks the edges so the panel floats forward. */}
      <div className="pointer-events-none absolute inset-0 grid-field opacity-60" />
      <div className="pointer-events-none absolute inset-0 bg-beam" />
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 90% at 50% 40%, transparent 45%, rgba(4,7,12,0.85) 100%)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(57,214,196,0.5), transparent)",
        }}
      />
      <div className="relative z-10 w-full max-w-sm">
        <LoginForm />
      </div>
    </div>
  );
}
