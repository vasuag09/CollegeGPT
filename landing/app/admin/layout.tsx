"use client";

import { useEffect, useState } from "react";

const SESSION_KEY = "nmgpt_admin_auth";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = sessionStorage.getItem(SESSION_KEY);
      if (stored) setAuthed(true);
      setChecking(false);
    }
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    try {
      const res = await fetch(`${apiUrl}/admin/stats`, {
        headers: { "X-Admin-Password": password },
      });
      if (res.ok) {
        sessionStorage.setItem(SESSION_KEY, password);
        setAuthed(true);
      } else {
        setError("Incorrect password.");
      }
    } catch {
      setError("Could not reach the server.");
    }
  }

  if (checking) return null;

  if (!authed) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <div className="mb-8 text-center">
            <p className="text-xs font-bold tracking-widest uppercase text-primary/80 mb-2">NM-GPT</p>
            <h1 className="text-xl font-bold text-foreground">Admin Dashboard</h1>
            <p className="text-sm text-muted mt-1">Enter your password to continue</p>
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Admin password"
              autoFocus
              className="w-full px-4 py-3 bg-surface border border-border rounded-xl text-foreground text-sm placeholder:text-muted focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition"
            />
            {error && <p className="text-xs text-red-400">{error}</p>}
            <button
              type="submit"
              className="w-full py-3 bg-primary/10 hover:bg-primary/20 border border-primary/25 hover:border-primary/50 text-primary rounded-xl font-semibold text-sm transition-all duration-200"
            >
              Sign In
            </button>
          </form>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
