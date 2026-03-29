"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface YearOption     { key: string; label: string }
interface SemOption      { label: string }
interface PortalOptions  {
  years:             YearOption[];
  semesters_by_year: Record<string, SemOption[]>;
  default_year:      string;
  default_semester:  string;
}
interface AttendanceRow {
  subject:     string;
  attended:    number;
  total:       number;
  not_updated: number;
  percentage:  number | null;
  last_entry:  string;
  pending:     number | null;   // course_total_hours − total_conducted
  to_attend:   number | null;   // ceil(0.8 × course_total_hours) − attended, clamped ≥ 0
}

type Step = "credentials" | "options" | "results";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DATE_RE = /^\d{2}\.\d{2}\.\d{4}$/;

function validateDate(val: string): string | null {
  if (!val) return null;
  if (!DATE_RE.test(val)) return "Use DD.MM.YYYY format";
  const [dd, mm, yyyy] = val.split(".").map(Number);
  if (mm < 1 || mm > 12) return "Invalid month";
  if (dd < 1 || dd > 31) return "Invalid day";
  if (yyyy < 2020 || yyyy > 2100) return "Invalid year";
  return null;
}

function Spinner() {
  return (
    <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

export default function AttendanceForm() {
  const [step, setStep]           = useState<Step>("credentials");
  const [sapId, setSapId]         = useState("");
  const [password, setPassword]   = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState<string | null>(null);

  // Step 2
  const [options, setOptions]             = useState<PortalOptions | null>(null);
  const [selectedYear, setSelectedYear]   = useState("");
  const [selectedSem, setSelectedSem]     = useState("");
  const [startDate, setStartDate]         = useState("");
  const [endDate, setEndDate]             = useState("");

  // Step 3
  const [subjects, setSubjects]       = useState<AttendanceRow[] | null>(null);
  const [manualHours, setManualHours] = useState<Record<string, string>>({});
  const [savingHours, setSavingHours] = useState<Record<string, boolean>>({});
  const [fetchSecs, setFetchSecs]     = useState<number | null>(null);
  const [fetchedAt, setFetchedAt]     = useState<string | null>(null);

  // Inline field errors
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // ── Step 1 → 2: fetch options ─────────────────────────────────
  const handleCredentials = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!sapId.trim()) errs.sapId = "SAP ID is required";
    else if (!/^\d{8,12}$/.test(sapId.trim())) errs.sapId = "SAP ID must be 8–12 digits";
    if (!password) errs.password = "Password is required";
    else if (password.length < 6) errs.password = "Password must be at least 6 characters";
    if (Object.keys(errs).length) { setFieldErrors(errs); return; }
    setFieldErrors({});
    setIsLoading(true);
    setError(null);
    try {
      const res  = await fetch(`${API_BASE}/attendance/options`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ sap_id: sapId.trim(), sap_password: password }),
      });
      const data = await res.json();
      if (data.error) { setError(data.error); return; }

      const opts: PortalOptions = data.options;
      setOptions(opts);
      setSelectedYear(opts.default_year);
      setSelectedSem(opts.default_semester ?? "");

      // Default dates: start of current year → today
      const today = new Date();
      const dd    = String(today.getDate()).padStart(2, "0");
      const mm    = String(today.getMonth() + 1).padStart(2, "0");
      const yyyy  = today.getFullYear();
      setEndDate(`${dd}.${mm}.${yyyy}`);
      setStartDate(`01.01.${yyyy}`);

      setStep("options");
    } catch {
      setError("Could not connect to the server. Make sure the backend is running.");
    } finally {
      setIsLoading(false);
      setPassword(""); // clear password after use
    }
  };

  // ── Step 2 → 3: fetch attendance ─────────────────────────────
  const handleFetch = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!password) errs.password = "Password is required";
    const startErr = validateDate(startDate);
    const endErr   = validateDate(endDate);
    if (startErr) errs.startDate = startErr;
    if (endErr)   errs.endDate   = endErr;
    if (startDate && endDate && !startErr && !endErr) {
      const [sd, sm, sy] = startDate.split(".").map(Number);
      const [ed, em, ey] = endDate.split(".").map(Number);
      const s = new Date(sy, sm - 1, sd), en = new Date(ey, em - 1, ed);
      if (en < s) errs.endDate = "End date must be after start date";
    }
    if (Object.keys(errs).length) { setFieldErrors(errs); return; }
    setFieldErrors({});
    setIsLoading(true);
    setError(null);
    const t0 = Date.now();
    try {
      const res  = await fetch(`${API_BASE}/attendance`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          sap_id:         sapId.trim(),
          sap_password:   password,          // re-entered in step 2 for security
          year_key:       selectedYear || null,
          semester_label: selectedSem  || null,
          start_date:     startDate    || null,
          end_date:       endDate      || null,
        }),
      });
      const data = await res.json();
      if (data.error) { setError(data.error); return; }
      setFetchSecs(Math.round((Date.now() - t0) / 1000));
      setFetchedAt(new Date().toLocaleTimeString());
      setSubjects(data.subjects);
      setStep("results");
    } catch {
      setError("Could not connect to the server.");
    } finally {
      setIsLoading(false);
      setPassword("");
    }
  };

  const handleSaveHours = async (subject: string) => {
    const hrs = parseInt(manualHours[subject] ?? "");
    if (!hrs || hrs < 1) return;
    setSavingHours(prev => ({ ...prev, [subject]: true }));
    try {
      const res = await fetch(`${API_BASE}/attendance/course-hours`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ subject, total_hours: hrs }),
      });
      if (res.ok) {
        setSubjects(prev => prev!.map(s => {
          if (s.subject !== subject) return s;
          const pending   = Math.max(0, hrs - s.total);
          const to_attend = Math.max(0, Math.ceil(0.8 * hrs) - s.attended);
          return { ...s, pending, to_attend };
        }));
        setManualHours(prev => { const n = { ...prev }; delete n[subject]; return n; });
      }
    } finally {
      setSavingHours(prev => ({ ...prev, [subject]: false }));
    }
  };

  const handleReset = () => {
    setStep("credentials");
    setSapId(""); setPassword("");
    setOptions(null); setSubjects(null);
    setError(null); setFieldErrors({});
    setSelectedYear(""); setSelectedSem("");
    setStartDate(""); setEndDate("");
    setFetchSecs(null); setFetchedAt(null);
  };

  // ── Results ───────────────────────────────────────────────────
  if (step === "results" && subjects !== null) {
    if (subjects.length === 0) {
      return (
        <div className="mt-3 text-sm text-muted">
          No attendance data found.{" "}
          <button onClick={handleReset} className="text-primary hover:underline">Try again</button>
        </div>
      );
    }
    const graded   = subjects.filter(r => r.percentage !== null);
    const totalAttended = graded.reduce((s, r) => s + r.attended, 0);
    const totalClasses  = graded.reduce((s, r) => s + r.total,    0);
    const overallPct    = totalClasses > 0 ? (totalAttended / totalClasses) * 100 : 0;

    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mt-3 overflow-x-auto"
      >
        {/* Fetch meta */}
        <p className="text-xs text-muted mb-2">
          {fetchedAt && <>Fetched at {fetchedAt}{fetchSecs !== null ? ` · took ${fetchSecs}s` : ""} · </>}
          <span className="font-medium text-foreground/70">{selectedSem}{selectedYear ? ` (${options?.years.find(y => y.key === selectedYear)?.label ?? selectedYear})` : ""}</span>
        </p>

        {/* Prompt to fill in missing course hours */}
        {subjects.some(s => s.to_attend === null) && (
          <p className="text-xs text-muted mb-2">
            Some subjects are missing total course hours — enter them in the{" "}
            <span className="text-foreground/70 font-medium">To attend / Pending</span>{" "}
            column and hit <span className="text-foreground/70 font-medium">Save</span> to see how many lectures you still need.
          </p>
        )}

        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-border/40">
              <th className="text-left py-2 pr-4 font-medium text-muted">Subject</th>
              <th className="text-right py-2 px-3 font-medium text-muted whitespace-nowrap">Attended</th>
              <th className="text-right py-2 px-3 font-medium text-muted whitespace-nowrap">%</th>
              <th className="text-right py-2 px-3 font-medium text-muted whitespace-nowrap" title="Lectures still needed to reach 80% of full course">To attend</th>
              <th className="text-right py-2 px-3 font-medium text-muted whitespace-nowrap" title="Lectures not yet conducted this semester">Pending</th>
              <th className="text-right py-2 font-medium text-muted whitespace-nowrap">Last entry</th>
            </tr>
          </thead>
          <tbody>
            {subjects.map((s, i) => {
              const isNU    = s.percentage === null;
              const isLow   = !isNU && s.percentage! < 80;
              const isSafe  = !isNU && s.to_attend === 0;
              return (
                <tr key={i} className={`border-b border-border/20 last:border-0 ${isNU ? "opacity-60" : ""}`}>
                  <td className="py-2 pr-4 text-foreground">
                    {s.subject}
                    {s.not_updated > 0 && !isNU && (
                      <span className="ml-2 text-xs text-muted">
                        (+{s.not_updated} not updated)
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums text-muted whitespace-nowrap">
                    {isNU ? `${s.not_updated} lecture${s.not_updated !== 1 ? "s" : ""}` : `${s.attended}/${s.total}`}
                  </td>
                  <td className={`py-2 px-3 text-right font-semibold tabular-nums ${isNU ? "text-muted italic" : isLow ? "text-amber-400" : "text-green-400"}`}>
                    {isNU ? "Not updated" : `${s.percentage!.toFixed(1)}%`}
                    {isLow && !isNU && <span className="ml-1 text-xs">⚠</span>}
                  </td>
                  {s.to_attend === null ? (
                    <td colSpan={2} className="py-1.5 px-3">
                      <form
                        onSubmit={e => { e.preventDefault(); handleSaveHours(s.subject); }}
                        className="flex items-center gap-1 justify-end"
                      >
                        <input
                          type="number" min="1" max="500"
                          value={manualHours[s.subject] ?? ""}
                          onChange={e => setManualHours(prev => ({ ...prev, [s.subject]: e.target.value }))}
                          placeholder="total hrs"
                          className="w-20 px-2 py-0.5 rounded bg-background border border-border text-xs text-foreground placeholder:text-muted focus:outline-none focus:border-primary/60 tabular-nums"
                        />
                        <button
                          type="submit"
                          disabled={savingHours[s.subject] || !manualHours[s.subject]}
                          className="px-2 py-0.5 rounded bg-primary/10 border border-primary/30 text-primary text-xs hover:bg-primary/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
                        >
                          {savingHours[s.subject] ? "…" : "Save"}
                        </button>
                      </form>
                    </td>
                  ) : (
                    <>
                      <td className={`py-2 px-3 text-right tabular-nums whitespace-nowrap ${
                        s.to_attend === 0 ? "text-green-400 font-medium" : "text-amber-400 font-medium"
                      }`}>
                        {s.to_attend === 0 ? "✓ Met" : `${s.to_attend} more`}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums text-muted whitespace-nowrap">
                        {s.pending}
                      </td>
                    </>
                  )}
                  <td className="py-2 text-right text-muted text-xs whitespace-nowrap">
                    {s.last_entry || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-border/40">
              <td className="py-2 pr-4 text-muted text-xs">Overall</td>
              <td className="py-2 px-3 text-right tabular-nums text-muted text-xs">
                {totalAttended}/{totalClasses}
              </td>
              <td className="py-2 px-3 text-right font-bold tabular-nums text-foreground">
                {overallPct.toFixed(1)}%
              </td>
              <td colSpan={3} />
            </tr>
          </tfoot>
        </table>
        {/* Disclaimer */}
        <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2.5 text-xs text-amber-300/80 space-y-1">
          <p className="font-medium text-amber-300">Important notes</p>
          <ul className="list-disc list-inside space-y-0.5 text-amber-200/70">
            <li>Extra / make-up class attendance may or may not appear here — it depends on whether the faculty has marked it on the portal.</li>
            <li>Always verify your attendance directly on the SAP portal before drawing any conclusions.</li>
            <li>The <em>Pending</em> column is based on the scheduled course hours and may not reflect actual classes yet to be held.</li>
          </ul>
        </div>

        <button onClick={handleReset}
          className="mt-3 text-xs text-muted hover:text-foreground transition-colors">
          Fetch again
        </button>
      </motion.div>
    );
  }

  // ── Options form (step 2) ─────────────────────────────────────
  if (step === "options" && options) {
    return (
      <motion.form
        initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        onSubmit={handleFetch}
        className="mt-3 space-y-3"
      >
        <p className="text-xs text-muted">Select report parameters then re-enter your password.</p>

        {/* Year */}
        <div>
          <label className="block text-xs text-muted mb-1">Academic Year</label>
          <select
            value={selectedYear}
            onChange={e => {
              const yr = e.target.value;
              setSelectedYear(yr);
              const sems = options.semesters_by_year[yr] ?? [];
              setSelectedSem(sems.length > 0 ? sems[sems.length - 1].label : "");
            }}
            disabled={isLoading}
            className="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-foreground focus:outline-none focus:border-primary/60 transition-colors"
          >
            {[...options.years].reverse().map(y => (
              <option key={y.key} value={y.key}>{y.label}</option>
            ))}
          </select>
        </div>

        {/* Semester */}
        <div>
          <label className="block text-xs text-muted mb-1">Semester</label>
          <select
            value={selectedSem}
            onChange={e => setSelectedSem(e.target.value)}
            disabled={isLoading}
            className="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-foreground focus:outline-none focus:border-primary/60 transition-colors"
          >
            {(options.semesters_by_year[selectedYear] ?? []).map(s => (
              <option key={s.label} value={s.label}>{s.label}</option>
            ))}
          </select>
        </div>

        {/* Date range */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-muted mb-1">From (DD.MM.YYYY)</label>
            <input
              type="text" value={startDate}
              onChange={e => { setStartDate(e.target.value); setFieldErrors(p => ({ ...p, startDate: "" })); }}
              placeholder="01.06.2025"
              disabled={isLoading}
              className={`w-full px-3 py-2 rounded-lg bg-background border text-sm text-foreground placeholder:text-muted focus:outline-none transition-colors ${fieldErrors.startDate ? "border-red-400/60 focus:border-red-400" : "border-border focus:border-primary/60"}`}
            />
            {fieldErrors.startDate && <p className="mt-0.5 text-xs text-red-400">{fieldErrors.startDate}</p>}
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">To (DD.MM.YYYY)</label>
            <input
              type="text" value={endDate}
              onChange={e => { setEndDate(e.target.value); setFieldErrors(p => ({ ...p, endDate: "" })); }}
              placeholder="28.03.2026"
              disabled={isLoading}
              className={`w-full px-3 py-2 rounded-lg bg-background border text-sm text-foreground placeholder:text-muted focus:outline-none transition-colors ${fieldErrors.endDate ? "border-red-400/60 focus:border-red-400" : "border-border focus:border-primary/60"}`}
            />
            {fieldErrors.endDate && <p className="mt-0.5 text-xs text-red-400">{fieldErrors.endDate}</p>}
          </div>
        </div>

        {/* Re-enter password */}
        <div>
          <label className="block text-xs text-muted mb-1">Password (re-enter to confirm)</label>
          <input
            type="password" value={password}
            onChange={e => { setPassword(e.target.value); setFieldErrors(p => ({ ...p, password: "" })); }}
            placeholder="SAP password"
            autoComplete="current-password"
            disabled={isLoading}
            className={`w-full px-3 py-2 rounded-lg bg-background border text-sm text-foreground placeholder:text-muted focus:outline-none transition-colors ${fieldErrors.password ? "border-red-400/60 focus:border-red-400" : "border-border focus:border-primary/60"}`}
          />
          {fieldErrors.password && <p className="mt-0.5 text-xs text-red-400">{fieldErrors.password}</p>}
        </div>

        {error && <p className="text-xs text-red-400">{error}</p>}

        <div className="flex gap-2">
          <button type="button" onClick={handleReset} disabled={isLoading}
            className="px-3 py-2 rounded-lg border border-border text-sm text-muted hover:text-foreground disabled:opacity-40 transition-colors">
            Back
          </button>
          <button type="submit"
            disabled={isLoading || !password || !selectedYear || !selectedSem}
            className="flex-1 py-2 rounded-lg bg-primary/10 border border-primary/30 text-primary text-sm font-medium hover:bg-primary/20 hover:border-primary/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-2">
            {isLoading ? <><Spinner /> Fetching… (may take 30–60s)</> : "Get Attendance"}
          </button>
        </div>
      </motion.form>
    );
  }

  // ── Credentials form (step 1) ─────────────────────────────────
  return (
    <motion.form
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      onSubmit={handleCredentials}
      className="mt-3 space-y-2.5"
    >
      <div>
        <label className="block text-xs text-muted mb-1">SAP ID</label>
        <input type="text" value={sapId}
          onChange={e => { setSapId(e.target.value); setFieldErrors(p => ({ ...p, sapId: "" })); }}
          placeholder="Enter your SAP ID" autoComplete="username" disabled={isLoading}
          className={`w-full px-3 py-2 rounded-lg bg-background border text-sm text-foreground placeholder:text-muted focus:outline-none transition-colors ${fieldErrors.sapId ? "border-red-400/60 focus:border-red-400" : "border-border focus:border-primary/60"}`}
        />
        {fieldErrors.sapId && <p className="mt-0.5 text-xs text-red-400">{fieldErrors.sapId}</p>}
      </div>
      <div>
        <label className="block text-xs text-muted mb-1">Password</label>
        <input type="password" value={password}
          onChange={e => { setPassword(e.target.value); setFieldErrors(p => ({ ...p, password: "" })); }}
          placeholder="Enter your SAP password" autoComplete="current-password" disabled={isLoading}
          className={`w-full px-3 py-2 rounded-lg bg-background border text-sm text-foreground placeholder:text-muted focus:outline-none transition-colors ${fieldErrors.password ? "border-red-400/60 focus:border-red-400" : "border-border focus:border-primary/60"}`}
        />
        {fieldErrors.password && <p className="mt-0.5 text-xs text-red-400">{fieldErrors.password}</p>}
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <button type="submit" disabled={isLoading || !sapId.trim() || !password}
        className="w-full py-2 rounded-lg bg-primary/10 border border-primary/30 text-primary text-sm font-medium hover:bg-primary/20 hover:border-primary/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-2">
        {isLoading ? <><Spinner /> Loading options…</> : "Continue →"}
      </button>
      <p className="text-xs text-muted">
        Credentials are sent directly to the SAP portal and are never stored.
      </p>
    </motion.form>
  );
}
