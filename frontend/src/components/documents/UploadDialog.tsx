import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Upload, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label, Select } from "@/components/ui/input";
import { uploadDocument } from "@/api/documents";

const CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"];
const ROLES = ["admin", "compliance_auditor", "analyst", "viewer"];

export function UploadDialog(): JSX.Element {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [classification, setClassification] = useState("internal");
  const [roles, setRoles] = useState<string[]>(["analyst"]);

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
          <Upload className="h-4 w-4" /> Upload
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2 animate-slide-up rounded-2xl border border-slate-200 bg-white p-6 shadow-glow focus:outline-none">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="text-base font-semibold text-slate-900">
              Upload document
            </Dialog.Title>
            <Dialog.Close className="grid h-8 w-8 place-items-center rounded-md text-slate-400 hover:bg-slate-100">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">
            Upload and ingest a document with a classification and allowed roles.
          </Dialog.Description>

          <div className="space-y-4">
            <div>
              <Label>File</Label>
              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-200 px-4 py-6 text-sm text-slate-500 transition-colors hover:border-indigo-300 hover:bg-indigo-50/30">
                <Upload className="h-4 w-4" />
                {file ? file.name : "Choose a file (pdf, docx, txt, md, html)"}
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
                {ROLES.map((r) => {
                  const active = roles.includes(r);
                  return (
                    <button
                      key={r}
                      type="button"
                      onClick={() => toggleRole(r)}
                      className={
                        active
                          ? "rounded-full bg-indigo-600 px-3 py-1 text-xs font-medium text-white"
                          : "rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200"
                      }
                    >
                      {r}
                    </button>
                  );
                })}
              </div>
            </div>

            {mutation.isError && (
              <p className="text-sm text-rose-600">{(mutation.error as Error).message}</p>
            )}

            <Button
              className="w-full"
              disabled={!file || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              {mutation.isPending ? "Ingesting…" : "Upload & ingest"}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
