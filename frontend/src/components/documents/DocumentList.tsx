import { useQuery } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";

import { listDocuments } from "@/api/documents";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { classificationTone } from "@/lib/ui";

export function DocumentList(): JSX.Element {
  const { data, isLoading, error } = useQuery({
    queryKey: ["documents"],
    queryFn: () => listDocuments(1, 50),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading documents…
      </div>
    );
  }
  if (error) return <p className="text-sm text-rose-600">{(error as Error).message}</p>;

  const items = data?.items ?? [];
  if (items.length === 0) {
    return (
      <Card className="grid place-items-center gap-2 p-12 text-center">
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-slate-100">
          <FileText className="h-6 w-6 text-slate-400" />
        </div>
        <p className="text-sm font-medium text-slate-600">No documents visible to you</p>
        <p className="text-xs text-slate-400">
          Documents you're authorized to see will appear here.
        </p>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50/60 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-5 py-3 font-medium">Document</th>
            <th className="px-5 py-3 font-medium">Classification</th>
            <th className="px-5 py-3 font-medium">Allowed roles</th>
            <th className="px-5 py-3 text-right font-medium">Chunks</th>
            <th className="px-5 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((d) => (
            <tr key={d.id} className="transition-colors hover:bg-slate-50/60">
              <td className="px-5 py-3">
                <div className="flex items-center gap-2.5">
                  <FileText className="h-4 w-4 shrink-0 text-slate-400" />
                  <span className="font-medium text-slate-700">{d.filename}</span>
                </div>
              </td>
              <td className="px-5 py-3">
                <Badge tone={classificationTone(d.classification)}>{d.classification}</Badge>
              </td>
              <td className="px-5 py-3 text-xs text-slate-500">{d.allowed_roles.join(", ")}</td>
              <td className="px-5 py-3 text-right font-mono text-slate-600">{d.chunk_count}</td>
              <td className="px-5 py-3">
                <Badge tone={d.status === "ready" ? "emerald" : "slate"}>{d.status}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
