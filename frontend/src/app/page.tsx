import Link from "next/link";

export default function HomePage() {
  return (
    <div className="relative mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-16">
      <div className="animate-rise">
        <p className="mb-4 text-sm uppercase tracking-[0.25em] text-[var(--muted)]">Knowledge, grounded</p>
        <h1 className="font-display text-5xl leading-tight md:text-7xl">Aconic</h1>
        <p className="mt-5 max-w-xl text-lg text-[var(--muted)]">
          Upload PDF, DOCX, or TXT files and ask questions answered from your documents — with
          retrieval-augmented generation.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/signup" className="btn btn-primary">
            Get started
          </Link>
          <Link href="/login" className="btn btn-ghost">
            Log in
          </Link>
        </div>
      </div>
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-64 opacity-40"
        style={{
          background:
            "linear-gradient(to top, rgba(61,155,110,0.25), transparent), repeating-linear-gradient(90deg, transparent, transparent 40px, rgba(232,240,234,0.04) 40px, rgba(232,240,234,0.04) 41px)",
        }}
      />
    </div>
  );
}
