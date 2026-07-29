export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
    processing: "bg-sky-500/15 text-sky-200 border-sky-500/30",
    ready: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
    failed: "bg-rose-500/15 text-rose-200 border-rose-500/30",
  };
  const cls = map[status] || "bg-white/10 text-white/80 border-white/20";
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs capitalize ${cls}`}>
      {status === "processing" ? <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current animate-pulse-soft" /> : null}
      {status}
    </span>
  );
}
