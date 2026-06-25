import { useQuery } from "@tanstack/react-query";

import { listDocuments } from "@/api/documents";

export function DocumentList(): JSX.Element {
  const { data, isLoading, error } = useQuery({
    queryKey: ["documents"],
    queryFn: () => listDocuments(1, 50),
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (error) return <p className="text-sm text-red-600">{(error as Error).message}</p>;

  const items = data?.items ?? [];
  return (
    <div className="rounded border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-500">
          <tr>
            <th className="p-2">Filename</th>
            <th className="p-2">Classification</th>
            <th className="p-2">Allowed roles</th>
            <th className="p-2">Chunks</th>
            <th className="p-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((d) => (
            <tr key={d.id} className="border-b border-slate-100">
              <td className="p-2">{d.filename}</td>
              <td className="p-2">{d.classification}</td>
              <td className="p-2 text-slate-500">{d.allowed_roles.join(", ")}</td>
              <td className="p-2">{d.chunk_count}</td>
              <td className="p-2">{d.status}</td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={5} className="p-3 text-center text-slate-400">
                No documents visible to you.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
