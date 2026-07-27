import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Upload, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label, Select } from "@/components/ui/input";
import { uploadDocument } from "@/api/documents";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"];
const ALL_ROLES = ["admin", "compliance_auditor", "analyst", "viewer"];

export function UploadDialog(): JSX.Element {
  const qc = useQueryClient();
  const { roles: myRoles } = useAuth();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [classification, setClassification] = useState("internal");

  // §6.18: only offer roles within the uploader's own authority — an admin may
  // grant any role, everyone else only the roles they hold. The API enforces the
  // same rule; this keeps the UI from proposing a request that would be refused.
  const grantable = myRoles.includes("admin")
    ? ALL_ROLES
    : ALL_ROLES.filter((r) => myRoles.includes(r));
  const [roles, setRoles] = useState<string[]>(() =>
    grantable.includes("analyst") ? ["analyst"] : grantable.slice(0, 1),
  );

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Select a file");
      return uploadDocument(file, classification, roles);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["documents"] });
      setFile(null);
      setOpen(false);
    },
  });

  const toggleRole = (role: string): void =>
    setRoles((r) => (r.includes(role) ? r.filter((x) => x !== role) : [...r, role]));

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button>
          <Upload className="h-4 w-4" /> Ingest
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-ink/70 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2 animate-slide-up rounded-lg border border-edge/15 bg-slab p-6 shadow-lift focus:outline-none">
          <div className="mb-1 flex items-center justify-between">
            <Dialog.Title className="text-base font-semibold text-fg">Ingest document</Dialog.Title>
            <Dialog.Close className="grid h-8 w-8 place-items-center rounded-md text-fg-faint hover:bg-raise hover:text-fg">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="mb-5 text-xs text-fg-faint">
            Parsed, chunked, embedded, and indexed locally. Classification and roles gate retrieval.
          </Dialog.Description>

          <div className="space-y-4">
            <div>
              <Label>File</Label>
              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-edge/20 bg-ink px-4 py-6 text-sm text-fg-dim transition-colors hover:border-beacon/40 hover:text-fg">
                <Upload className="h-4 w-4" />
                {file ? file.name : "Choose a file · pdf, docx, txt, md, html"}
                <input
                  type="file"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </div>

            <div>
              <Label htmlFor="cls">Classification</Label>
              <Select
                id="cls"
                value={classification}
                onChange={(e) => setClassification(e.target.value)}
              >
                {CLASSIFICATIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <Label>Allowed roles</Label>
              <div className="flex flex-wrap gap-2">
                {grantable.map((r) => {
                  const active = roles.includes(r);
                  return (
                    <button
                      key={r}
                      type="button"
                      onClick={() => toggleRole(r)}
                      className={cn(
                        "rounded-md px-3 py-1 font-mono text-[11px] font-medium uppercase tracking-wider ring-1 ring-inset transition-colors",
                        active
                          ? "bg-beacon/15 text-beacon ring-beacon/40"
                          : "bg-ink text-fg-faint ring-edge/15 hover:text-fg-dim",
                      )}
                    >
                      {r}
                    </button>
                  );
                })}
              </div>
            </div>

            {mutation.isError && (
              <p className="text-sm text-crimson">{(mutation.error as Error).message}</p>
            )}

            <Button
              className="w-full"
              disabled={!file || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              {mutation.isPending ? "Ingesting…" : "Ingest & index"}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
