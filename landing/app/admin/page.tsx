"use client";

import { useEffect, useState, useCallback } from "react";

const SESSION_KEY = "nmgpt_admin_auth";

interface Stats {
  totals: { today: number; week: number; all_time: number };
  answer_types: Record<string, number>;
  avg_confidence: number;
  avg_latency_ms: number;
  hourly: { hour: string; count: number }[];
  top_questions: { question: string; count: number }[];
}

// ── Tiny stat card ────────────────────────────────────────────
function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-surface border border-border rounded-2xl px-5 py-4">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted mb-1">{label}</p>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      {sub && <p className="text-xs text-muted mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Inline SVG bar chart (no dependencies) ───────────────────
function HourlyChart({ data }: { data: { hour: string; count: number }[] }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  const W = 700;
  const H = 120;
  const barW = Math.floor(W / data.length) - 2;

  return (
    <div className="bg-surface border border-border rounded-2xl px-5 py-4">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted mb-3">
        Queries — last 24 hours
      </p>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H + 24}`}
          className="w-full"
          style={{ minWidth: 480 }}
          aria-label="Hourly query chart"
        >
          {data.map((d, i) => {
            const barH = Math.round((d.count / max) * H);
            const x = i * (barW + 2);
            const y = H - barH;
            const isZero = d.count === 0;
            return (
              <g key={d.hour}>
                <rect
                  x={x}
                  y={isZero ? H - 2 : y}
                  width={barW}
                  height={isZero ? 2 : barH}
                  rx={3}
                  className={isZero ? "fill-border" : "fill-primary/60"}
                />
                {/* label every 4 hours */}
                {i % 4 === 0 && (
                  <text
                    x={x + barW / 2}
                    y={H + 16}
                    textAnchor="middle"
                    fontSize={9}
                    className="fill-muted"
                  >
                    {d.hour}
                  </text>
                )}
                {/* count on top for non-zero */}
                {d.count > 0 && (
                  <text
                    x={x + barW / 2}
                    y={y - 3}
                    textAnchor="middle"
                    fontSize={8}
                    className="fill-primary"
                  >
                    {d.count}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

// ── Answer type pills ─────────────────────────────────────────
const TYPE_COLORS: Record<string, string> = {
  rag:        "bg-blue-500/15 text-blue-300 border-blue-500/25",
  pyq:        "bg-amber-500/15 text-amber-300 border-amber-500/25",
  greeting:   "bg-green-500/15 text-green-300 border-green-500/25",
  attendance: "bg-purple-500/15 text-purple-300 border-purple-500/25",
  error:      "bg-red-500/15 text-red-300 border-red-500/25",
};

function AnswerTypes({ types }: { types: Record<string, number> }) {
  const total = Object.values(types).reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="bg-surface border border-border rounded-2xl px-5 py-4">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted mb-3">Answer types</p>
      <div className="flex flex-wrap gap-2">
        {Object.entries(types).map(([type, count]) => (
          <span
            key={type}
            className={`px-3 py-1.5 rounded-lg border text-xs font-semibold ${
              TYPE_COLORS[type] ?? "bg-surface border-border text-muted"
            }`}
          >
            {type} — {count} ({Math.round((count / total) * 100)}%)
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Top questions list ────────────────────────────────────────
function TopQuestions({ questions }: { questions: { question: string; count: number }[] }) {
  return (
    <div className="bg-surface border border-border rounded-2xl px-5 py-4">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted mb-3">
        Top questions (last 7 days)
      </p>
      {questions.length === 0 ? (
        <p className="text-sm text-muted">No data yet.</p>
      ) : (
        <ol className="space-y-2">
          {questions.map((q, i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="text-[10px] font-bold text-muted/60 mt-0.5 w-4 shrink-0">
                {i + 1}.
              </span>
              <span className="text-sm text-foreground flex-1 leading-snug">{q.question}</span>
              <span className="text-xs text-muted shrink-0 font-semibold">×{q.count}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────
export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError("");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const password = sessionStorage.getItem(SESSION_KEY) ?? "";
    try {
      const res = await fetch(`${apiUrl}/admin/stats`, {
        headers: { "X-Admin-Password": password },
      });
      if (!res.ok) {
        setError(`Server returned ${res.status}`);
        return;
      }
      const data: Stats = await res.json();
      setStats(data);
    } catch (e) {
      setError(`Failed to load stats: ${String(e)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30_000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  function handleLogout() {
    sessionStorage.removeItem(SESSION_KEY);
    window.location.reload();
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top bar */}
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div>
          <p className="text-[10px] font-bold tracking-widest uppercase text-primary/80">NM-GPT</p>
          <h1 className="text-lg font-bold text-foreground leading-none mt-0.5">Admin Dashboard</h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchStats}
            className="text-xs font-semibold text-muted hover:text-foreground transition-colors flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <button
            onClick={handleLogout}
            className="text-xs font-semibold text-muted hover:text-red-400 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {loading && (
          <div className="flex items-center justify-center h-48">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-950/25 border border-red-500/25 text-red-300 text-sm px-5 py-4 rounded-2xl">
            {error}
          </div>
        )}

        {stats && !loading && (
          <>
            {/* Stat cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <StatCard label="Today" value={stats.totals.today} />
              <StatCard label="This week" value={stats.totals.week} />
              <StatCard label="All time" value={stats.totals.all_time} />
              <StatCard
                label="Avg latency"
                value={`${stats.avg_latency_ms} ms`}
                sub={`${Math.round(stats.avg_confidence * 100)}% avg confidence`}
              />
            </div>

            {/* Hourly chart */}
            <HourlyChart data={stats.hourly} />

            {/* Answer types */}
            <AnswerTypes types={stats.answer_types} />

            {/* Top questions */}
            <TopQuestions questions={stats.top_questions} />
          </>
        )}
      </main>
    </div>
  );
}
