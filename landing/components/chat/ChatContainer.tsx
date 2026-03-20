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
}

// ── Constants ───────────────────────────────────────────────

const STREAM_URL = "http://localhost:8000/query/stream";
const TOP_K = 5;

// ── Component ───────────────────────────────────────────────

export default function ChatContainer() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

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

      try {
        const response = await fetch(STREAM_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, top_k: TOP_K }),
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
              // Mark streaming complete
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMsgId
                    ? { ...msg, isStreaming: false }
                    : msg
                )
              );
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
      } catch (err) {
        const errorMessage =
          err instanceof Error
            ? err.message
            : "Something went wrong. Please try again.";

        const isConnectionError =
          errorMessage.includes("Failed to fetch") ||
          errorMessage.includes("NetworkError") ||
          errorMessage.includes("ERR_CONNECTION_REFUSED");

        // If we already added an AI message for streaming, update it
        setMessages((prev) => {
          const hasStreamingMsg = prev.some((m) => m.id === aiMsgId);
          if (hasStreamingMsg) {
            return prev.map((msg) =>
              msg.id === aiMsgId
                ? {
                    ...msg,
                    content: isConnectionError
                      ? "Unable to connect to the NM-GPT server. Make sure the backend is running on localhost:8000."
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
                ? "Unable to connect to the NM-GPT server. Make sure the backend is running on localhost:8000."
                : errorMessage,
              isError: true,
            },
          ];
        });
      } finally {
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
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  citations={msg.citations}
                  pages={msg.pages}
                  confidence={msg.confidence}
                  isError={msg.isError}
                  onRetry={msg.isError ? handleRetry : undefined}
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
