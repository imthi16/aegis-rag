import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { uploadDocument } from "@/api/documents";

const CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"];
const ROLES = ["admin", "compliance_auditor", "analyst", "viewer"];

export function UploadDialog(): JSX.Element {
  const qc = useQueryClient();
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
    },
  });

  const toggleRole = (role: string): void =>
    setRoles((r) => (r.includes(role) ? r.filter((x) => x !== role) : [...r, role]));

  return (
    <div className="rounded border border-slate-200 bg-white p-4">
      <h3 className="mb-2 font-semibold text-slate-700">Upload document</h3>
      <input
        type="file"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="mb-2 block text-sm"
      />
      <label className="mb-2 block text-sm">
        Classification
        <select
          value={classification}
          onChange={(e) => setClassification(e.target.value)}
          className="ml-2 rounded border border-slate-300 px-2 py-1"
        >
          {CLASSIFICATIONS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <div className="mb-2 flex flex-wrap gap-3 text-sm">
        {ROLES.map((r) => (
          <label key={r} className="flex items-center gap-1">
            <input type="checkbox" checked={roles.includes(r)} onChange={() => toggleRole(r)} />
            {r}
          </label>
        ))}
      </div>
      <button
        type="button"
        disabled={!file || mutation.isPending}
        onClick={() => mutation.mutate()}
        className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
      >
        {mutation.isPending ? "Uploading…" : "Upload"}
      </button>
      {mutation.isError && (
        <p className="mt-2 text-sm text-red-600">{(mutation.error as Error).message}</p>
      )}
    </div>
  );
}
