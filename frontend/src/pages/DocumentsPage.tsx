import { FileText } from "lucide-react";

import { DocumentList } from "@/components/documents/DocumentList";
import { UploadDialog } from "@/components/documents/UploadDialog";
import { PageHeader } from "@/components/layout/PageHeader";
import { useAuth } from "@/hooks/useAuth";

export function DocumentsPage(): JSX.Element {
  const { hasRole } = useAuth();
  const canUpload = hasRole("analyst") || hasRole("admin");
  return (
    <div className="flex h-screen flex-col">
      <PageHeader
        eyebrow="Corpus"
        title="Documents"
        subtitle="RBAC-filtered — you see only what your roles authorize"
        icon={<FileText className="h-5 w-5" />}
        actions={canUpload ? <UploadDialog /> : undefined}
      />
      <div className="scroll-slim flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl">
          <DocumentList />
        </div>
      </div>
    </div>
  );
}
