"use client";

import { useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export default function ChatInput({ value, onChange, onSend, disabled }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && hasText && !isTooLong) onSend();
    }
  };

  const MAX_LENGTH = 500;
  const hasText = value.trim().length > 0;
  const isTooLong = value.length > MAX_LENGTH;

  return (
    <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 pb-5 pt-3">
      {/* Input card */}
      <div className="relative group">
        {/* Amber glow on focus */}
        <div className="absolute -inset-px rounded-2xl bg-gradient-to-r from-primary/40 via-accent/30 to-primary/40 opacity-0 group-focus-within:opacity-100 transition-opacity duration-400 blur-sm" />

        <div className="relative flex items-end gap-3 bg-surface border border-border rounded-2xl px-4 py-3 shadow-2xl shadow-black/40 focus-within:border-primary/40 transition-colors duration-300">
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about policies, exams, attendance, or anything campus…"
            rows={1}
            disabled={disabled}
            className="flex-1 text-sm py-1.5 bg-transparent focus:outline-none placeholder:text-muted/60 text-foreground disabled:opacity-40 leading-relaxed resize-none max-h-[200px] custom-scrollbar"
          />

          {/* Send button */}
          <motion.button
            whileHover={{ scale: hasText && !disabled ? 1.05 : 1 }}
            whileTap={{ scale: hasText && !disabled ? 0.92 : 1 }}
            onClick={onSend}
            disabled={disabled || !hasText || isTooLong}
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200"
            style={{
              background: hasText && !disabled
                ? "linear-gradient(135deg, #f59e0b, #d97706)"
                : "rgba(28, 28, 50, 0.6)",
              boxShadow: hasText && !disabled
                ? "0 4px 14px rgba(245, 158, 11, 0.3)"
                : "none",
              opacity: disabled ? 0.35 : 1,
            }}
            aria-label="Send message"
          >
            <svg
              className="w-4 h-4"
              style={{ color: hasText && !disabled ? "white" : "#64748b" }}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </motion.button>
        </div>
      </div>

      {/* Footer hint */}
      <div className="flex items-center justify-between mt-2.5 px-1">
        <span className="text-[10px] text-muted/50 font-medium tracking-wide">
          Answers sourced from official NMIMS documents · Shift+Enter for newline
        </span>
        <span
          className={`text-[10px] font-medium tabular-nums ${
            isTooLong ? "text-red-400" : "text-muted/35"
          }`}
        >
          {value.length}/{MAX_LENGTH}
        </span>
      </div>
    </div>
  );
}
