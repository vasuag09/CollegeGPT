"use client";

import { useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
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
      if (!disabled && value.trim()) {
        onSend();
      }
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 sm:px-6 pb-6 pt-2">
      <div className="relative group">
        {/* Glow effect on focus */}
        <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/30 to-accent/30 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition duration-500" />
        
        <div className="relative flex items-end gap-2 bg-surface border border-border rounded-2xl p-2 pl-4 shadow-xl focus-within:border-primary/50 transition-all duration-300">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about attendance, exams, or policies..."
            rows={1}
            disabled={disabled}
            className="flex-1 text-[15px] py-3 bg-transparent focus:outline-none placeholder:text-muted text-foreground disabled:opacity-50 leading-relaxed resize-none max-h-[200px] custom-scrollbar"
          />
          
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onSend}
            disabled={disabled || !value.trim()}
            className="w-11 h-11 rounded-xl bg-primary hover:bg-primary-dark text-white flex items-center justify-center shrink-0 disabled:opacity-20 disabled:grayscale transition-all duration-200 shadow-lg shadow-primary/20"
            aria-label="Send message"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 12h14M12 5l7 7-7 7"
              />
            </svg>
          </motion.button>
        </div>
      </div>
      
      <p className="text-[11px] text-center text-muted mt-3 font-medium tracking-wide">
        NM-GPT is powered by the Student Resource Book. Responses may be summarized.
      </p>
    </div>
  );
}
