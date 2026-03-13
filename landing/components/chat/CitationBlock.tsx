"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Citation {
  text: string;
  page_start: number;
  page_end: number;
  chunk_id: string;
}

interface CitationBlockProps {
  citations: Citation[];
  pages: number[];
  confidence: number;
}

export default function CitationBlock({
  citations,
  pages,
  confidence,
}: CitationBlockProps) {
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  // Deduplicate pages and sort
  const uniquePages = [...new Set(pages)].sort((a, b) => a - b);

  // Format page ranges: [32, 33, 34, 40] -> ["32-34", "40"]
  const formatPageRanges = (nums: number[]): string[] => {
    if (nums.length === 0) return [];
    const ranges: string[] = [];
    let start = nums[0];
    let end = nums[0];
    for (let i = 1; i < nums.length; i++) {
      if (nums[i] === end + 1) {
        end = nums[i];
      } else {
        ranges.push(start === end ? `${start}` : `${start}\u2013${end}`);
        start = nums[i];
        end = nums[i];
      }
    }
    ranges.push(start === end ? `${start}` : `${start}\u2013${end}`);
    return ranges;
  };

  const pageRanges = formatPageRanges(uniquePages);
  const confidencePercent = Math.round(confidence * 100);

  return (
    <div className="space-y-3">
      {/* Header with Source Info */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-muted uppercase tracking-wider">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.331 0 4.467.89 6.064 2.346m0-12.304a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.346m0-12.304v12.304" />
          </svg>
          Sources
        </div>

        <div className="flex flex-wrap gap-1.5">
          {pageRanges.map((range) => (
            <span
              key={range}
              className="px-2 py-0.5 rounded-md bg-bubble-ai border border-border text-[11px] font-medium text-foreground/80"
            >
              SRB Page {range}
            </span>
          ))}
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <div className="w-16 h-1.5 rounded-full bg-border overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${confidencePercent}%` }}
              className="h-full bg-primary rounded-full"
            />
          </div>
          <span className="text-[10px] font-bold text-muted uppercase tracking-tight">
            {confidencePercent}% match
          </span>
        </div>
      </div>

      {/* Toggle View Source Button */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-[11px] font-semibold text-muted hover:text-primary transition-all duration-200"
      >
        <span className={`w-4 h-4 rounded-full border border-border flex items-center justify-center transition-transform ${expanded ? "rotate-180" : ""}`}>
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M19 9l-7 7-7-7" />
          </svg>
        </span>
        {expanded ? "Hide evidence" : "Show evidence from SRB"}
      </button>

      {/* Expanded evidence content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-2">
              {citations.map((citation, i) => (
                <div
                  key={citation.chunk_id || i}
                  className="p-3 bg-surface border border-border rounded-xl shadow-sm"
                >
                  <div className="flex items-center gap-2 mb-2 text-[10px] font-bold text-muted uppercase tracking-widest">
                    <span className="w-1 h-1 rounded-full bg-primary" />
                    Excerpt from Page {citation.page_start}
                  </div>
                  <p className="text-[13px] leading-relaxed text-muted/90 italic">
                    &quot;{citation.text}&quot;
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
