"use client";

import { motion } from "framer-motion";

interface EmptyStateProps {
  onSelectPrompt: (prompt: string) => void;
}

const suggestions = [
  {
    title: "Check My Attendance",
    prompt: "check my attendance",
    source: "SAP Portal",
    color: "teal",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    title: "Attendance Policy",
    prompt: "What is the minimum attendance requirement for NMIMS students?",
    source: "SRB",
    color: "amber",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
    ),
  },
  {
    title: "Exam Schedule",
    prompt: "When are the Term End Exams for Semester I and Semester II?",
    source: "Academic Calendar",
    color: "violet",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    title: "UFM Consequences",
    prompt: "What are the penalties for using unfair means during examinations?",
    source: "UFM Policy",
    color: "rose",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
  },
  {
    title: "TEE Exam Rules",
    prompt: "What are the instructions and rules for appearing in TEE examinations?",
    source: "Exam Instructions",
    color: "sky",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5S19.832 5.477 21 6.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
    ),
  },
  {
    title: "Code of Conduct",
    prompt: "What is the student code of conduct during university examinations?",
    source: "Code of Conduct",
    color: "emerald",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    title: "Question Papers",
    prompt: "Do you have question papers for Calculus?",
    source: "Drive",
    color: "orange",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
];

const colorMap: Record<string, { bg: string; text: string; border: string; sourceBg: string; sourceText: string }> = {
  teal:    { bg: "rgba(20,184,166,0.08)",  text: "#2dd4bf", border: "rgba(20,184,166,0.15)",  sourceBg: "rgba(20,184,166,0.1)",  sourceText: "#5eead4" },
  amber:   { bg: "rgba(245,158,11,0.08)",  text: "#f59e0b", border: "rgba(245,158,11,0.15)",  sourceBg: "rgba(245,158,11,0.1)",  sourceText: "#fbbf24" },
  violet:  { bg: "rgba(139,92,246,0.08)",  text: "#a78bfa", border: "rgba(139,92,246,0.15)",  sourceBg: "rgba(139,92,246,0.1)",  sourceText: "#c4b5fd" },
  rose:    { bg: "rgba(244,63,94,0.08)",   text: "#fb7185", border: "rgba(244,63,94,0.15)",   sourceBg: "rgba(244,63,94,0.1)",   sourceText: "#fda4af" },
  sky:     { bg: "rgba(14,165,233,0.08)",  text: "#38bdf8", border: "rgba(14,165,233,0.15)",  sourceBg: "rgba(14,165,233,0.1)",  sourceText: "#7dd3fc" },
  emerald: { bg: "rgba(16,185,129,0.08)",  text: "#34d399", border: "rgba(16,185,129,0.15)",  sourceBg: "rgba(16,185,129,0.1)",  sourceText: "#6ee7b7" },
  orange:  { bg: "rgba(249,115,22,0.08)",  text: "#fb923c", border: "rgba(249,115,22,0.15)",  sourceBg: "rgba(249,115,22,0.1)",  sourceText: "#fdba74" },
};

export default function EmptyState({ onSelectPrompt }: EmptyStateProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6 py-8 sm:py-12 max-w-3xl mx-auto w-full">

      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.19, 1, 0.22, 1] }}
        className="text-center mb-10"
      >
        {/* Icon with ambient glow */}
        <div className="relative w-20 h-20 mx-auto mb-6">
          <div className="absolute inset-0 rounded-3xl bg-primary/20 blur-xl animate-float" />
          <div className="relative w-20 h-20 rounded-3xl bg-surface border border-primary/20 flex items-center justify-center shadow-lg shadow-primary/10">
            <svg className="w-10 h-10 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.4}
                d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
        </div>

        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground mb-2">
          Ask anything about <span className="gradient-text">NMIMS</span>
        </h1>
        <p className="text-muted text-base max-w-sm mx-auto leading-relaxed">
          Instant answers from official university documents — policies, schedules, rules, and more.
        </p>
      </motion.div>

      {/* Suggestion cards — 2×3 grid */}
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {suggestions.map((item, index) => {
          const c = colorMap[item.color];
          return (
            <motion.button
              key={item.title}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.07 + 0.2, duration: 0.4, ease: [0.19, 1, 0.22, 1] }}
              onClick={() => onSelectPrompt(item.prompt)}
              className="suggestion-card flex flex-col items-start p-4 rounded-2xl text-left group hover:border-opacity-60"
              style={{
                background: "var(--color-surface)",
                borderColor: c.border,
              }}
            >
              {/* Icon */}
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center mb-3 transition-transform duration-200 group-hover:scale-110"
                style={{ background: c.bg, color: c.text }}
              >
                {item.icon}
              </div>

              {/* Title + source */}
              <div className="flex items-start justify-between w-full gap-2 mb-1.5">
                <h3 className="font-semibold text-sm text-foreground leading-tight">{item.title}</h3>
                <span
                  className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md shrink-0"
                  style={{ background: c.sourceBg, color: c.sourceText }}
                >
                  {item.source}
                </span>
              </div>

              <p className="text-[11px] text-muted leading-relaxed line-clamp-2">
                {item.prompt}
              </p>
            </motion.button>
          );
        })}
      </div>

      {/* Bottom hint */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="mt-8 text-[11px] text-muted/60 text-center"
      >
        Powered by official NMIMS documents · Ask "pyq for &lt;subject&gt;" for question papers
      </motion.p>
    </div>
  );
}
