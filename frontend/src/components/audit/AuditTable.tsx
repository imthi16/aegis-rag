import { useMutation, useQuery } from "@tanstack/react-query";
import { Link2, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";

import { listAudit, verifyChain } from "@/api/audit";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fingerprint, outcomeTone } from "@/lib/ui";
import type { AuditEntry, ChainReport } from "@/types/api";

function outcomeDot(outcome: string): string {
  switch (outcome) {
    case "success":
      return "bg-jade";
    case "denied":
      return "bg-gold";
    case "error":
      return "bg-crimson";
    default:
      return "bg-edge";
  }
}

function LedgerNode({
  entry,
  broken,
  last,
}: {
  entry: AuditEntry;
  broken: boolean;
  last: boolean;
}): JSX.Element {
  return (
    <li className="relative pl-10">
      {/* Chain spine + link node */}
      {!last && (
        <span
          className={cn(
            "absolute left-[15px] top-6 h-[calc(100%-4px)] w-px",
            broken ? "bg-crimson/40" : "bg-edge/20",
          )}
        />
      )}
      <span
        className={cn(
          "absolute left-[9px] top-4 grid h-3.5 w-3.5 place-items-center rounded-full ring-4 ring-ink",
          "shadow-[inset_0_1px_0_rgba(255,255,255,0.45),0_2px_5px_rgba(0,0,0,0.7)]",
          broken ? "bg-crimson" : outcomeDot(entry.outcome),
        )}
      />

      <div
        className={cn(
          "hw mb-2.5 px-4 py-3 transition-transform duration-200 hover:-translate-y-0.5 hover:shadow-e2",
          broken && "border-crimson/40",
        )}
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <span className="font-mono text-[11px] text-fg-faint">
            #{String(entry.id).padStart(4, "0")}
          </span>
          <span className="font-mono text-sm font-medium text-fg">{entry.action}</span>
          <Badge tone={outcomeTone(entry.outcome)}>{entry.outcome}</Badge>
          <span className="ml-auto font-mono text-[11px] text-fg-faint">
            {new Date(entry.ts).toLocaleString()}
          </span>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-fg-dim">
          <span className="flex items-center gap-1.5">
            <Link2 className="h-3 w-3 text-fg-faint" />
            <span className="text-fg-faint">prev</span> {fingerprint(entry.prev_hash)}
            <span className="text-fg-faint">→</span>
            <span className={broken ? "text-crimson" : "text-beacon"}>
              {fingerprint(entry.entry_hash)}
            </span>
          </span>
          <span className="text-fg-faint">
            {entry.resource_type}
            {entry.resource_id ? `/${fingerprint(entry.resource_id, 6, 0)}` : ""}
          </span>
        </div>
      </div>
    </li>
  );
}

export function AuditTable(): JSX.Element {
  const { data, isLoading, error } = useQuery({
    queryKey: ["audit"],
    queryFn: () => listAudit(1, 50),
  });
  const verify = useMutation<ChainReport, Error>({ mutationFn: () => verifyChain() });

  const items = [...(data?.items ?? [])].sort((a, b) => b.id - a.id);
  const brokenId = verify.data && !verify.data.ok ? verify.data.first_broken_id : null;

  return (
    <div className="space-y-4">
      {/* Chain integrity instrument */}
      <div className="hw flex flex-wrap items-center justify-between gap-3 px-4 py-3.5">
        <div>
          <div className="eyebrow mb-1">// Chain integrity</div>
          <p className="text-sm text-fg-dim">Recompute every HMAC link end-to-end.</p>
        </div>
        <div className="flex items-center gap-3">
          {verify.data &&
            (verify.data.ok ? (
              <span className="inline-flex animate-stamp items-center gap-1.5 rounded-md bg-beacon/10 px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-beacon ring-1 ring-inset ring-beacon/40">
                <ShieldCheck className="h-4 w-4" /> Intact · {verify.data.total}
              </span>
            ) : (
              <span className="inline-flex animate-stamp items-center gap-1.5 rounded-md bg-crimson/10 px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-crimson ring-1 ring-inset ring-crimson/40">
                <ShieldAlert className="h-4 w-4" /> Broken #{verify.data.first_broken_id} ·{" "}
                {verify.data.broken_field}
              </span>
            ))}
          <Button onClick={() => verify.mutate()} disabled={verify.isPending}>
            {verify.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Verify chain
          </Button>
        </div>
      </div>

      {/* The ledger spine */}
      <div className="relative overflow-hidden rounded-md">
        {verify.isPending && (
          <div
            className="pointer-events-none absolute inset-x-0 top-0 z-10 h-16 animate-scan"
            style={{
              background:
                "linear-gradient(180deg, transparent, rgba(57,214,196,0.14) 60%, rgba(57,214,196,0.55))",
            }}
          />
        )}
        {isLoading ? (
          <div className="flex items-center gap-2 rounded-md border border-edge/12 bg-slab p-5 text-sm text-fg-dim">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading ledger…
          </div>
        ) : error ? (
          <p className="rounded-md border border-crimson/30 bg-slab p-5 text-sm text-crimson">
            {(error as Error).message}
          </p>
        ) : items.length === 0 ? (
          <p className="rounded-md border border-edge/12 bg-slab p-5 text-sm text-fg-faint">
            No audit entries yet.
          </p>
        ) : (
          <ul className="pt-1">
            {items.map((a, i) => (
              <LedgerNode
                key={a.id}
                entry={a}
                broken={brokenId !== null && a.id === brokenId}
                last={i === items.length - 1}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
