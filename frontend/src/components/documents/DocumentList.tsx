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
      <div className="flex items-center gap-2 text-sm text-fg-dim">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading corpus…
      </div>
    );
  }
  if (error) return <p className="text-sm text-crimson">{(error as Error).message}</p>;

  const items = data?.items ?? [];
  if (items.length === 0) {
    return (
      <Card className="grid place-items-center gap-2 p-12 text-center">
        <div className="grid h-12 w-12 place-items-center rounded-md border border-edge/12 bg-ink text-fg-faint">
          <FileText className="h-6 w-6" />
        </div>
        <p className="text-sm font-medium text-fg">No documents visible to you</p>
        <p className="text-xs text-fg-faint">
          Only documents your roles authorize will appear here.
        </p>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-edge/12 bg-ink/40">
          <tr className="font-mono text-[10px] uppercase tracking-eyebrow text-fg-faint">
            <th className="px-5 py-3 font-medium">Document</th>
            <th className="px-5 py-3 font-medium">Classification</th>
            <th className="px-5 py-3 font-medium">Allowed roles</th>
            <th className="px-5 py-3 text-right font-medium">Chunks</th>
            <th className="px-5 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-edge/8">
          {items.map((d) => (
            <tr key={d.id} className="transition-colors hover:bg-raise/40">
              <td className="px-5 py-3">
                <div className="flex items-center gap-2.5">
                  <FileText className="h-4 w-4 shrink-0 text-fg-faint" />
                  <span className="font-medium text-fg">{d.filename}</span>
                </div>
              </td>
              <td className="px-5 py-3">
                <Badge tone={classificationTone(d.classification)}>{d.classification}</Badge>
              </td>
              <td className="px-5 py-3 font-mono text-xs text-fg-dim">
                {d.allowed_roles.join(" · ")}
              </td>
              <td className="px-5 py-3 text-right font-mono text-fg-dim tabular-nums">
                {d.chunk_count}
              </td>
              <td className="px-5 py-3">
                <Badge tone={d.status === "ready" ? "jade" : "slate"}>{d.status}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
