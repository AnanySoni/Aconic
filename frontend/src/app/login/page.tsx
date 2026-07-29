"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiLogin } from "@/lib/api";
import { saveTokens } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const tokens = await apiLogin(email, password);
      saveTokens(tokens.access_token, tokens.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <div className="surface animate-rise rounded-2xl p-8">
        <Link href="/" className="font-display text-2xl">
          Aconic
        </Link>
        <h1 className="mt-6 text-xl font-semibold">Log in</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">Access your knowledge base</p>
        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-1 block text-sm text-[var(--muted)]">Email</label>
            <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-sm text-[var(--muted)]">Password</label>
            <input
              className="input"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
          <button className="btn btn-primary w-full" disabled={loading}>
            {loading ? "Signing in…" : "Log in"}
          </button>
        </form>
        <p className="mt-4 text-sm text-[var(--muted)]">
          No account?{" "}
          <Link href="/signup" className="text-[var(--accent)]">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
