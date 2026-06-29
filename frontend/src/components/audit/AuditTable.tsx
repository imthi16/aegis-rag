import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, ShieldAlert, ShieldCheck } from "lucide-react";

import { listAudit, verifyChain } from "@/api/audit";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { outcomeTone } from "@/lib/ui";
import type { ChainReport } from "@/types/api";

export function AuditTable(): JSX.Element {
  const { data, isLoading, error } = useQuery({
    queryKey: ["audit"],
    queryFn: () => listAudit(1, 50),
  });
  const verify = useMutation<ChainReport, Error>({ mutationFn: () => verifyChain() });

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <ShieldCheck className="h-4 w-4 text-indigo-500" />
          Verify the tamper-evident hash chain end-to-end.
        </div>
        <div className="flex items-center gap-3">
          {verify.data &&
            (verify.data.ok ? (
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                <ShieldCheck className="h-4 w-4" /> Intact · {verify.data.total} entries
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-rose-50 px-3 py-1.5 text-sm font-medium text-rose-700 ring-1 ring-inset ring-rose-600/20">
                <ShieldAlert className="h-4 w-4" /> Broken at #{verify.data.first_broken_id} (
                {verify.data.broken_field})
              </span>
            ))}
          <Button onClick={() => verify.mutate()} disabled={verify.isPending}>
            {verify.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Verify chain
          </Button>
        </div>
      </Card>

      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="flex items-center gap-2 p-5 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading audit trail…
          </div>
        ) : error ? (
          <p className="p-5 text-sm text-rose-600">{(error as Error).message}</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50/60 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 font-medium">#</th>
                <th className="px-5 py-3 font-medium">Timestamp</th>
                <th className="px-5 py-3 font-medium">Action</th>
                <th className="px-5 py-3 font-medium">Outcome</th>
                <th className="px-5 py-3 font-medium">Resource</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(data?.items ?? []).map((a) => (
                <tr key={a.id} className="transition-colors hover:bg-slate-50/60">
                  <td className="px-5 py-2.5 font-mono text-xs text-slate-400">{a.id}</td>
                  <td className="px-5 py-2.5 text-xs text-slate-500">
                    {new Date(a.ts).toLocaleString()}
                  </td>
                  <td className="px-5 py-2.5 font-medium text-slate-700">{a.action}</td>
                  <td className="px-5 py-2.5">
                    <Badge tone={outcomeTone(a.outcome)}>{a.outcome}</Badge>
                  </td>
                  <td className="px-5 py-2.5 text-xs text-slate-500">
                    {a.resource_type}
                    {a.resource_id ? `/${a.resource_id.slice(0, 8)}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
