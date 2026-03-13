"use client";

import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CitationBlock from "./CitationBlock";

interface Citation {
  text: string;
  page_start: number;
  page_end: number;
  chunk_id: string;
}

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  pages?: number[];
  confidence?: number;
  isError?: boolean;
  onRetry?: () => void;
}

export default function MessageBubble({
  role,
  content,
  citations,
  pages,
  confidence,
  isError,
  onRetry,
}: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.19, 1, 0.22, 1] }}
      className={`flex gap-4 ${isUser ? "justify-end" : "justify-start"} mb-6`}
    >
      {/* AI Avatar */}
      {!isUser && (
        <div className="flex w-9 h-9 rounded-xl bg-surface border border-border items-center justify-center shrink-0 mt-1 shadow-sm">
          <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
        </div>
      )}

      {/* Message content */}
      <div className={`max-w-[85%] sm:max-w-[70%] ${isUser ? "flex justify-end" : ""}`}>
        <div
          className={`px-5 py-4 rounded-2xl shadow-sm ${
            isUser
              ? "chat-message-user rounded-tr-sm"
              : isError
              ? "bg-red-950/30 border border-red-500/30 text-red-200 rounded-tl-sm"
              : "chat-message-ai rounded-tl-sm"
          }`}
        >
          {/* Content */}
          {isUser || isError ? (
            <p className="text-[15px] leading-relaxed whitespace-pre-wrap">
              {content}
            </p>
          ) : (
            <div className="prose-chat text-[15px] leading-relaxed">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}

          {/* Error retry */}
          {isError && onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 text-xs font-semibold text-red-400 hover:text-red-300 flex items-center gap-2 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Try reconnecting
            </button>
          )}

          {/* Citations block */}
          {!isUser && !isError && citations && citations.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border/50">
              <CitationBlock
                citations={citations}
                pages={pages || []}
                confidence={confidence || 0}
              />
            </div>
          )}
        </div>
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex w-9 h-9 rounded-xl bg-primary items-center justify-center shrink-0 mt-1 shadow-md border border-white/10">
          <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </div>
      )}
    </motion.div>
  );
}

/** Typing indicator component */
export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-4 justify-start mb-6"
    >
      <div className="flex w-9 h-9 rounded-xl bg-surface border border-border items-center justify-center shrink-0 mt-1">
        <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        </svg>
      </div>
      <div className="chat-message-ai px-5 py-4 rounded-2xl rounded-tl-sm">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full typing-dot" />
          <div className="w-2 h-2 rounded-full typing-dot" />
          <div className="w-2 h-2 rounded-full typing-dot" />
        </div>
      </div>
    </motion.div>
  );
}
