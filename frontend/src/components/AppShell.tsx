"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearTokens } from "@/lib/auth";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/chat", label: "AI Chat" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[#0f1c18]/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link href="/dashboard" className="font-display text-xl tracking-tight">
            Aconic
          </Link>
          <nav className="flex items-center gap-2">
            {links.map((link) => {
              const active = pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-1.5 text-sm transition ${
                    active ? "bg-[var(--bg-soft)] text-white" : "text-[var(--muted)] hover:text-white"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
            <button
              className="btn btn-ghost ml-2"
              onClick={() => {
                clearTokens();
                router.push("/login");
              }}
            >
              Log out
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
