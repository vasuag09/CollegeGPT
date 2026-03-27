"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface AttendanceSubject {
  subject: string;
  percentage: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function AttendanceForm() {
  const [sapId, setSapId] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [subjects, setSubjects] = useState<AttendanceSubject[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sapId.trim() || !password) return;

    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/attendance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sap_id: sapId.trim(), sap_password: password }),
      });

      const data = await res.json();

      if (data.error) {
        setError(data.error);
      } else {
        setSubjects(data.subjects);
      }
    } catch {
      setError("Could not connect to the server. Make sure the backend is running.");
    } finally {
      setIsLoading(false);
      // Clear password from state immediately after submission
      setPassword("");
    }
  };

  const handleReset = () => {
    setSubjects(null);
    setError(null);
    setSapId("");
    setPassword("");
  };

  // ── Result table ─────────────────────────────────────────
  if (subjects !== null) {
    if (subjects.length === 0) {
      return (
        <div className="mt-3 text-sm text-muted">
          No attendance data found. The portal may have returned an empty page.{" "}
          <button onClick={handleReset} className="text-primary hover:underline">
            Try again
          </button>
        </div>
      );
    }

    const overall =
      subjects.reduce((sum, s) => sum + s.percentage, 0) / subjects.length;

    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mt-3 overflow-x-auto"
      >
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-border/40">
              <th className="text-left py-2 pr-4 font-medium text-muted">Subject</th>
              <th className="text-right py-2 font-medium text-muted">Attendance</th>
            </tr>
          </thead>
          <tbody>
            {subjects.map((s, i) => {
              const isLow = s.percentage < 75;
              return (
                <tr key={i} className="border-b border-border/20 last:border-0">
                  <td className="py-2 pr-4 text-foreground">
                    {s.subject}
                    {isLow && (
                      <span className="ml-2 text-xs text-amber-400">⚠ below 75%</span>
                    )}
                  </td>
                  <td
                    className={`py-2 text-right font-semibold tabular-nums ${
                      isLow ? "text-amber-400" : "text-green-400"
                    }`}
                  >
                    {s.percentage.toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-border/40">
              <td className="py-2 pr-4 text-muted text-xs">Overall average</td>
              <td className="py-2 text-right font-bold tabular-nums text-foreground">
                {overall.toFixed(1)}%
              </td>
            </tr>
          </tfoot>
        </table>
        <button
          onClick={handleReset}
          className="mt-3 text-xs text-muted hover:text-foreground transition-colors"
        >
          Fetch again
        </button>
      </motion.div>
    );
  }

  // ── Credential form ──────────────────────────────────────
  return (
    <motion.form
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      onSubmit={handleSubmit}
      className="mt-3 space-y-2.5"
    >
      <div>
        <label className="block text-xs text-muted mb-1">SAP ID</label>
        <input
          type="text"
          value={sapId}
          onChange={(e) => setSapId(e.target.value)}
          placeholder="Enter your SAP ID"
          autoComplete="username"
          className="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-foreground placeholder:text-muted focus:outline-none focus:border-primary/60 transition-colors"
          disabled={isLoading}
        />
      </div>

      <div>
        <label className="block text-xs text-muted mb-1">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter your SAP password"
          autoComplete="current-password"
          className="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-foreground placeholder:text-muted focus:outline-none focus:border-primary/60 transition-colors"
          disabled={isLoading}
        />
      </div>

      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}

      <button
        type="submit"
        disabled={isLoading || !sapId.trim() || !password}
        className="w-full py-2 rounded-lg bg-primary/10 border border-primary/30 text-primary text-sm font-medium hover:bg-primary/20 hover:border-primary/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Fetching attendance…
          </>
        ) : (
          "Get Attendance"
        )}
      </button>

      <p className="text-xs text-muted">
        Your credentials are sent directly to the SAP portal and are never stored.
      </p>
    </motion.form>
  );
}
