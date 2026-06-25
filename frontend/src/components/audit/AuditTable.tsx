import { useMutation, useQuery } from "@tanstack/react-query";

import { listAudit, verifyChain } from "@/api/audit";
import type { ChainReport } from "@/types/api";

export function AuditTable(): JSX.Element {
  const { data, isLoading, error } = useQuery({
    queryKey: ["audit"],
    queryFn: () => listAudit(1, 50),
  });
  const verify = useMutation<ChainReport, Error>({ mutationFn: () => verifyChain() });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => verify.mutate()}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white"
        >
          Verify chain
        </button>
        {verify.data && (
          <span
            className={
              verify.data.ok
                ? "rounded bg-green-100 px-2 py-0.5 text-sm text-green-700"
                : "rounded bg-red-100 px-2 py-0.5 text-sm text-red-700"
            }
          >
            {verify.data.ok
              ? `OK · ${verify.data.total} entries`
              : `BROKEN at #${verify.data.first_broken_id} (${verify.data.broken_field})`}
          </span>
        )}
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {error && <p className="text-sm text-red-600">{(error as Error).message}</p>}

      <div className="rounded border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500">
            <tr>
              <th className="p-2">#</th>
              <th className="p-2">ts</th>
              <th className="p-2">action</th>
              <th className="p-2">outcome</th>
              <th className="p-2">resource</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((a) => (
              <tr key={a.id} className="border-b border-slate-100">
                <td className="p-2">{a.id}</td>
                <td className="p-2 text-slate-500">{new Date(a.ts).toLocaleString()}</td>
                <td className="p-2">{a.action}</td>
                <td className="p-2">{a.outcome}</td>
                <td className="p-2 text-slate-500">
                  {a.resource_type}
                  {a.resource_id ? `/${a.resource_id.slice(0, 8)}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
