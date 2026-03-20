"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Citation {
  text: string;
  page_start: number;
  page_end: number;
  chunk_id: string;
  source?: string;
}

interface CitationBlockProps {
  citations: Citation[];
  pages: number[];
  confidence: number;
}

export default function CitationBlock({ citations, pages, confidence }: CitationBlockProps) {
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  const uniquePages = [...new Set(pages)].sort((a, b) => a - b);

  const formatPageRanges = (nums: number[]): string[] => {
    if (nums.length === 0) return [];
    const ranges: string[] = [];
    let start = nums[0];
    let end = nums[0];
    for (let i = 1; i < nums.length; i++) {
      if (nums[i] === end + 1) {
        end = nums[i];
      } else {
        ranges.push(start === end ? `${start}` : `${start}–${end}`);
        start = nums[i];
        end = nums[i];
      }
    }
    ranges.push(start === end ? `${start}` : `${start}–${end}`);
    return ranges;
  };

  const pageRanges = formatPageRanges(uniquePages);
  const confidencePercent = Math.round(confidence * 100);
  const confidenceColor = confidencePercent >= 70 ? "#f59e0b" : confidencePercent >= 40 ? "#38bdf8" : "#94a3b8";

  // Get unique source documents
  const sources = [...new Set(citations.map(c => c.source).filter(Boolean))];

  return (
    <div className="space-y-2.5">
      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Source doc label */}
        <div className="flex items-center gap-1.5 text-[10px] font-bold text-muted uppercase tracking-widest">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Sources
        </div>

        {/* Page pills */}
        {pageRanges.map((range) => (
          <span
            key={range}
            className="px-2 py-0.5 rounded-md text-[10px] font-semibold citation-pill"
          >
            p.{range}
          </span>
        ))}

        {/* Source doc pills */}
        {sources.length > 0 && sources.map((src) => (
          <span
            key={src}
            className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-surface border border-border text-muted/80 max-w-[120px] truncate"
          >
            {src}
          </span>
        ))}

        {/* Confidence */}
        <div className="flex items-center gap-1.5 ml-auto">
          <div className="w-14 h-1 rounded-full bg-border overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${confidencePercent}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="h-full rounded-full"
              style={{ background: confidenceColor }}
            />
          </div>
          <span className="text-[9px] font-bold uppercase tracking-tight" style={{ color: confidenceColor }}>
            {confidencePercent}%
          </span>
        </div>
      </div>

      {/* Toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-[11px] font-medium text-muted hover:text-primary transition-colors duration-200"
      >
        <motion.span
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="w-3.5 h-3.5 rounded-full border border-border flex items-center justify-center"
        >
          <svg className="w-2 h-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M19 9l-7 7-7-7" />
          </svg>
        </motion.span>
        {expanded ? "Hide excerpts" : `View ${citations.length} source excerpt${citations.length > 1 ? "s" : ""}`}
      </button>

      {/* Expanded excerpts */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="mt-1 space-y-2">
              {citations.map((citation, i) => (
                <div
                  key={citation.chunk_id || i}
                  className="p-3 bg-surface border border-border rounded-xl"
                  style={{ borderLeft: "2px solid rgba(245,158,11,0.25)" }}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-[9px] font-bold text-muted/70 uppercase tracking-widest">
                      {citation.source ? `${citation.source} · ` : ""}Page {citation.page_start}
                    </span>
                  </div>
                  <p className="text-[12px] leading-relaxed text-muted/80 italic">
                    &ldquo;{citation.text}&rdquo;
                  </p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
