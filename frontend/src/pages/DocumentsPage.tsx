import { DocumentList } from "@/components/documents/DocumentList";
import { UploadDialog } from "@/components/documents/UploadDialog";
import { useAuth } from "@/hooks/useAuth";

export function DocumentsPage(): JSX.Element {
  const { hasRole } = useAuth();
  const canUpload = hasRole("analyst") || hasRole("admin");
  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <h1 className="text-xl font-semibold text-slate-800">Documents</h1>
      {canUpload && <UploadDialog />}
      <DocumentList />
    </div>
  );
}
