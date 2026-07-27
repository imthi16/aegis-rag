import { LoginForm } from "@/components/auth/LoginForm";
import { SovereignSeal3D } from "@/components/layout/SovereignSeal3D";

// The three promises the perimeter makes — stated plainly, in the product's
// own mono voice. Order is exposure → record → honesty, the arc of a query.
const GUARANTEES = [
  { term: "Air-gapped", detail: "Inference, embeddings, and index run on-premise. Nothing leaves." },
  { term: "Hash-chained audit", detail: "Every access appends to a tamper-evident record." },
  { term: "Answers cited or refused", detail: "Each claim traces to a source, or the system declines." },
] as const;

export function LoginPage(): JSX.Element {
  return (
    <div className="relative min-h-screen overflow-hidden bg-ink">
      {/* Instrument backdrop, built in depth planes: a receding grid, a beacon
          beam, and a vignette that sinks the edges so the panes float forward. */}
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
          background: "linear-gradient(90deg, transparent, rgba(57,214,196,0.5), transparent)",
        }}
      />

      <div className="relative z-10 grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
        {/* ── Hero / thesis (desktop) ─────────────────────────────────────── */}
        <section className="hidden flex-col justify-center gap-9 px-16 xl:px-24 lg:flex">
          <div className="scene-3d h-44 w-44">
            <SovereignSeal3D className="h-full w-full" />
          </div>

          <div>
            <h1 className="font-mono text-6xl font-semibold leading-none tracking-[0.14em] text-fg">
              AEGIS
            </h1>
            <p className="eyebrow mt-4">Sovereign RAG Terminal</p>
          </div>

          <p className="max-w-md text-[15px] leading-relaxed text-fg-dim">
            Question a private corpus from inside a sealed perimeter. Every answer is traced to its
            source. Every access is written to a record that can&rsquo;t be rewritten.
          </p>

          <div className="max-w-md border-t border-edge/12 pt-6">
            <ul className="space-y-4">
              {GUARANTEES.map(({ term, detail }) => (
                <li key={term} className="flex gap-3">
                  <span
                    aria-hidden
                    className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-beacon shadow-beacon"
                  />
                  <div>
                    <div className="font-mono text-[12px] uppercase tracking-eyebrow text-fg">
                      {term}
                    </div>
                    <div className="mt-1 text-[13px] leading-snug text-fg-faint">{detail}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── Auth faceplate ──────────────────────────────────────────────── */}
        <section className="relative flex items-center justify-center p-6 sm:p-10">
          {/* Seam: a hairline with a beacon bloom, dividing hero from lock. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-y-0 left-0 hidden w-px lg:block"
            style={{
              background:
                "linear-gradient(180deg, transparent, rgba(57,214,196,0.35), transparent)",
            }}
          />
          <div className="w-full max-w-sm">
            <LoginForm />
          </div>
        </section>
      </div>
    </div>
  );
}
