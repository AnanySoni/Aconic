"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import { apiDeleteDocument, apiDocuments, apiUpload, DocumentItem } from "@/lib/api";
import { requireAuthClient } from "@/lib/auth";

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DashboardPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const needsPoll = useMemo(
    () => docs.some((d) => d.status === "pending" || d.status === "processing"),
    [docs],
  );

  const load = useCallback(async () => {
    try {
      const token = requireAuthClient();
      const data = await apiDocuments(token);
      setDocs(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!needsPoll) return;
    const id = setInterval(load, 2500);
    return () => clearInterval(id);
  }, [needsPoll, load]);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    setError(null);
    try {
      const token = requireAuthClient();
      for (const file of Array.from(files)) {
        await apiUpload(token, file);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function removeDoc(id: string) {
    try {
      const token = requireAuthClient();
      await apiDeleteDocument(token, id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <AppShell>
      <div className="animate-rise space-y-8">
        <div>
          <h1 className="font-display text-3xl">Documents</h1>
          <p className="mt-1 text-[var(--muted)]">Upload PDF, DOCX, or TXT. We extract text and index it for Q&A.</p>
        </div>

        <div
          className={`surface rounded-2xl border-dashed p-10 text-center transition ${
            dragOver ? "border-[var(--accent)] bg-[var(--bg-soft)]" : ""
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
        >
          <p className="text-lg font-medium">{uploading ? "Uploading…" : "Drop files here"}</p>
          <p className="mt-1 text-sm text-[var(--muted)]">or choose from your computer</p>
          <label className="btn btn-primary mt-5 cursor-pointer">
            Select files
            <input
              type="file"
              className="hidden"
              accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              multiple
              disabled={uploading}
              onChange={(e) => handleFiles(e.target.files)}
            />
          </label>
        </div>

        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}

        <div className="surface overflow-hidden rounded-2xl">
          <div className="border-b border-[var(--line)] px-4 py-3 text-sm text-[var(--muted)]">
            {docs.length} document{docs.length === 1 ? "" : "s"}
          </div>
          {docs.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-[var(--muted)]">No documents yet.</p>
          ) : (
            <ul className="divide-y divide-[var(--line)]">
              {docs.map((doc) => (
                <li key={doc.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-4">
                  <div>
                    <p className="font-medium">{doc.filename}</p>
                    <p className="text-xs text-[var(--muted)]">
                      {formatBytes(doc.file_size)} · {new Date(doc.created_at).toLocaleString()}
                    </p>
                    {doc.error_message ? (
                      <p className="mt-1 text-xs text-[var(--danger)]">{doc.error_message}</p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={doc.status} />
                    <button className="btn btn-ghost text-xs" onClick={() => removeDoc(doc.id)}>
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </AppShell>
  );
}
