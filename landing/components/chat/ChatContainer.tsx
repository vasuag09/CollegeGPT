"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import MessageBubble, { TypingIndicator } from "./MessageBubble";
import ChatInput from "./ChatInput";
import EmptyState from "./EmptyState";

// ── Types ───────────────────────────────────────────────────

interface Citation {
  text: string;
  page_start: number;
  page_end: number;
  chunk_id: string;
  source?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  pages?: number[];
  confidence?: number;
  isError?: boolean;
  isStreaming?: boolean;
  suggestedFollowUps?: string[];
}

// ── Follow-up suggestions ────────────────────────────────────

const TOPIC_FOLLOW_UPS: Array<{ keywords: string[]; suggestions: string[] }> = [
  { keywords: ["attendance", "absent", "condonation", "75"],
    suggestions: ["Can I get attendance condonation for medical reasons?", "What happens if my attendance drops below 75%?"] },
  { keywords: ["exam", "tee", "hall", "admit", "paper"],
    suggestions: ["What documents do I need to carry to the exam hall?", "Can I apply for revaluation of my answer sheet?"] },
  { keywords: ["ufm", "unfair", "malpractice", "cheat", "penalty", "offence"],
    suggestions: ["What are the penalties for UFM offences?", "Is there an appeal process for UFM decisions?"] },
  { keywords: ["fee", "fees", "payment", "scholarship", "refund"],
    suggestions: ["What is the fee refund policy?", "Are there any scholarships available?"] },
  { keywords: ["backlog", "ktkt", "fail", "grace", "pass"],
    suggestions: ["What is the grace marks policy?", "How many attempts are allowed for backlog subjects?"] },
  { keywords: ["revaluation", "reassessment", "marks", "result", "scorecard"],
    suggestions: ["How do I apply for revaluation?", "What is the deadline for revaluation applications?"] },
  { keywords: ["leave", "medical", "sick", "certificate", "doctor"],
    suggestions: ["What documents are needed for a medical leave application?", "Does medical leave count towards attendance?"] },
  { keywords: ["hostel", "accommodation", "room", "mess"],
    suggestions: ["What are the hostel rules and regulations?", "How do I apply for hostel accommodation?"] },
];

function generateFollowUps(question: string): string[] {
  const q = question.toLowerCase();
  for (const entry of TOPIC_FOLLOW_UPS) {
    if (entry.keywords.some((kw) => q.includes(kw))) {
      return entry.suggestions.slice(0, 2);
    }
  }
  return [];
}

// ── Constants ───────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STREAM_URL = `${API_BASE}/query/stream`;
const TOP_K = 5;
const REQUEST_TIMEOUT_MS = 60_000;

// ── Component ───────────────────────────────────────────────

export default function ChatContainer() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom on new messages / streaming updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Generate a unique ID
  const genId = () =>
    `msg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

  // ── Send message (streaming) ────────────────────────────

  const sendMessage = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || isLoading) return;

      // Add user message
      const userMsg: Message = {
        id: genId(),
        role: "user",
        content: question,
      };

      const aiMsgId = genId();

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setIsLoading(true);

      // Create abort controller for timeout
      const controller = new AbortController();
      abortControllerRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

      try {
        const response = await fetch(STREAM_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, top_k: TOP_K }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          throw new Error(
            errorData?.detail || `Server error (${response.status})`
          );
        }

        if (!response.body) {
          throw new Error("ReadableStream not supported");
        }

        // Add the empty AI message that we'll stream into
        setMessages((prev) => [
          ...prev,
          {
            id: aiMsgId,
            role: "assistant",
            content: "",
            isStreaming: true,
          },
        ]);

        // Read the SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE lines from buffer
          const lines = buffer.split("\n");
          // Keep the last potentially incomplete line in the buffer
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data: ")) continue;

            const jsonStr = trimmed.slice(6);
            let event: {
              type: string;
              content?: string;
              citations?: Citation[];
              pages?: number[];
              confidence?: number;
              message?: string;
            };

            try {
              event = JSON.parse(jsonStr);
            } catch {
              continue;
            }

            if (event.type === "token" && event.content) {
              // Append token to the streaming message
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMsgId
                    ? { ...msg, content: msg.content + event.content }
                    : msg
                )
              );
            } else if (event.type === "citations") {
              // Attach citations to the message
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMsgId
                    ? {
                        ...msg,
                        citations: event.citations,
                        pages: event.pages,
                        confidence: event.confidence,
                      }
                    : msg
                )
              );
            } else if (event.type === "done") {
              // Mark streaming complete and attach follow-up suggestions
              setMessages((msgs) => {
                const userQ = [...msgs].reverse().find((m) => m.role === "user")?.content ?? "";
                return msgs.map((msg) =>
                  msg.id === aiMsgId
                    ? { ...msg, isStreaming: false, suggestedFollowUps: generateFollowUps(userQ) }
                    : msg
                );
              });
            } else if (event.type === "error") {
              // Replace streaming message with error
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMsgId
                    ? {
                        ...msg,
                        content:
                          event.message || "An error occurred.",
                        isError: true,
                        isStreaming: false,
                      }
                    : msg
                )
              );
            }
          }
        }

        // Stream ended without explicit "done" — clear the streaming flag
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === aiMsgId && msg.isStreaming
              ? { ...msg, isStreaming: false }
              : msg
          )
        );
      } catch (err) {
        const isAbort = err instanceof DOMException && err.name === "AbortError";
        const errorMessage = isAbort
          ? "Request timed out. The server took too long to respond."
          : err instanceof Error
          ? err.message
          : "Something went wrong. Please try again.";

        const isConnectionError =
          !isAbort && (
            errorMessage.includes("Failed to fetch") ||
            errorMessage.includes("NetworkError") ||
            errorMessage.includes("ERR_CONNECTION_REFUSED")
          );

        // If we already added an AI message for streaming, update it
        setMessages((prev) => {
          const hasStreamingMsg = prev.some((m) => m.id === aiMsgId);
          if (hasStreamingMsg) {
            return prev.map((msg) =>
              msg.id === aiMsgId
                ? {
                    ...msg,
                    content: isConnectionError
                      ? "Unable to connect to the NM-GPT server. Make sure the backend is running."
                      : errorMessage,
                    isError: true,
                    isStreaming: false,
                  }
                : msg
            );
          }
          // If streaming message wasn't added yet, add error message
          return [
            ...prev,
            {
              id: aiMsgId,
              role: "assistant" as const,
              content: isConnectionError
                ? "Unable to connect to the NM-GPT server. Make sure the backend is running."
                : errorMessage,
              isError: true,
            },
          ];
        });
      } finally {
        clearTimeout(timeoutId);
        abortControllerRef.current = null;
        setIsLoading(false);
      }
    },
    [isLoading]
  );

  // ── Retry last failed message ───────────────────────────

  const handleRetry = useCallback(() => {
    const lastUserMsg = [...messages]
      .reverse()
      .find((m) => m.role === "user");
    if (!lastUserMsg) return;

    setMessages((prev) => prev.filter((m) => !m.isError));
    sendMessage(lastUserMsg.content);
  }, [messages, sendMessage]);

  // ── Handle send ─────────────────────────────────────────

  const handleSend = () => {
    sendMessage(input);
  };

  const handlePromptSelect = (text: string) => {
    sendMessage(text);
  };

  // ── Render ──────────────────────────────────────────────

  const isEmpty = messages.length === 0;

  // Show typing indicator only while loading AND before the first token arrives
  const showTyping =
    isLoading &&
    !messages.some((m) => m.isStreaming && m.content.length > 0);

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background relative">
      {/* Messages area */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto custom-scrollbar">
        {isEmpty ? (
          <EmptyState onSelectPrompt={handlePromptSelect} />
        ) : (
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
            <div className="space-y-2">
              {messages.map((msg, i) => (
                <MessageBubble
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  citations={msg.citations}
                  pages={msg.pages}
                  confidence={msg.confidence}
                  isError={msg.isError}
                  onRetry={msg.isError ? handleRetry : undefined}
                  suggestedFollowUps={
                    i === messages.length - 1 && !msg.isStreaming
                      ? msg.suggestedFollowUps
                      : undefined
                  }
                  onSuggestionClick={handlePromptSelect}
                />
              ))}

              {showTyping && <TypingIndicator />}
            </div>

            <div ref={messagesEndRef} className="h-4" />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="shrink-0">
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          disabled={isLoading}
        />
      </div>
    </div>
  );
}
