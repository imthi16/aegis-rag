import { AuditTable } from "@/components/audit/AuditTable";

export function AuditPage(): JSX.Element {
  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <h1 className="text-xl font-semibold text-slate-800">Audit trail</h1>
      <AuditTable />
    </div>
  );
}
