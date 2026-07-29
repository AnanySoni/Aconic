"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { apiAskStream, apiDocuments, apiHistory, DocumentItem, HistoryItem } from "@/lib/api";
import { requireAuthClient } from "@/lib/auth";

type ChatMessage = { role: "user" | "assistant"; content: string };

export default function ChatPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMeta = useCallback(async () => {
    const token = requireAuthClient();
    const [documents, hist] = await Promise.all([apiDocuments(token), apiHistory(token)]);
    setDocs(documents.filter((d) => d.status === "ready"));
    setHistory(hist.items);
  }, []);

  useEffect(() => {
    loadMeta().catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [loadMeta]);

  function toggleDoc(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    const q = question.trim();
    setQuestion("");
    setMessages((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "" }]);
    setLoading(true);
    setError(null);
    try {
      const token = requireAuthClient();
      await apiAskStream(token, q, selected, (tokenText) => {
        setMessages((m) => {
          const copy = [...m];
          const last = copy[copy.length - 1];
          if (last?.role === "assistant") {
            copy[copy.length - 1] = { ...last, content: last.content + tokenText };
          }
          return copy;
        });
      });
      const hist = await apiHistory(token);
      setHistory(hist.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ask failed");
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        if (last?.role === "assistant" && !last.content) {
          copy[copy.length - 1] = { ...last, content: "Sorry — I could not generate an answer." };
        }
        return copy;
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="animate-rise grid gap-6 lg:grid-cols-[240px_1fr_260px]">
        <aside className="surface h-fit rounded-2xl p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Documents</h2>
          <p className="mt-1 text-xs text-[var(--muted)]">Leave empty to search all ready docs.</p>
          <ul className="mt-3 space-y-2">
            {docs.length === 0 ? (
              <li className="text-sm text-[var(--muted)]">No ready documents. Upload on the dashboard.</li>
            ) : (
              docs.map((d) => (
                <li key={d.id}>
                  <label className="flex cursor-pointer items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={selected.includes(d.id)}
                      onChange={() => toggleDoc(d.id)}
                    />
                    <span className="leading-snug">{d.filename}</span>
                  </label>
                </li>
              ))
            )}
          </ul>
        </aside>

        <section className="surface flex min-h-[70vh] flex-col rounded-2xl">
          <div className="border-b border-[var(--line)] px-4 py-3">
            <h1 className="font-display text-2xl">AI Chat</h1>
            <p className="text-sm text-[var(--muted)]">Answers are grounded in your uploaded content.</p>
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {messages.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">
                Try: “Summarize this document”, “What are the key points?”, or “What is the refund policy?”
              </p>
            ) : (
              messages.map((m, idx) => (
                <div
                  key={`${m.role}-${idx}`}
                  className={`max-w-[90%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${
                    m.role === "user" ? "ml-auto bg-[var(--accent-strong)] text-white" : "bg-[var(--bg-soft)]"
                  }`}
                >
                  {m.content || (loading && idx === messages.length - 1 ? "Thinking…" : "")}
                </div>
              ))
            )}
          </div>
          {error ? <p className="px-4 text-sm text-[var(--danger)]">{error}</p> : null}
          <form onSubmit={onSubmit} className="flex gap-2 border-t border-[var(--line)] p-4">
            <input
              className="input"
              placeholder="Ask a question about your documents…"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={loading}
            />
            <button className="btn btn-primary shrink-0" disabled={loading || !question.trim()}>
              {loading ? "…" : "Ask"}
            </button>
          </form>
        </section>

        <aside className="surface h-fit max-h-[70vh] overflow-y-auto rounded-2xl p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">History</h2>
          <ul className="mt-3 space-y-3">
            {history.length === 0 ? (
              <li className="text-sm text-[var(--muted)]">No questions yet.</li>
            ) : (
              history.map((h) => (
                <li key={h.id} className="rounded-lg bg-[var(--bg-soft)] p-2 text-xs">
                  <p className="font-medium text-white/90">{h.question}</p>
                  <p className="mt-1 line-clamp-3 text-[var(--muted)]">{h.answer}</p>
                </li>
              ))
            )}
          </ul>
        </aside>
      </div>
    </AppShell>
  );
}
