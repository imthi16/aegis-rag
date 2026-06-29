import { ScrollText } from "lucide-react";

import { AuditTable } from "@/components/audit/AuditTable";
import { PageHeader } from "@/components/layout/PageHeader";

export function AuditPage(): JSX.Element {
  return (
    <div className="flex h-screen flex-col">
      <PageHeader
        title="Audit trail"
        subtitle="Hash-chained, tamper-evident record of every sensitive action"
        icon={<ScrollText className="h-5 w-5" />}
      />
      <div className="scroll-slim flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl">
          <AuditTable />
        </div>
      </div>
    </div>
  );
}
