"use client";

import { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import ChatContainer from "@/components/chat/ChatContainer";
import type { Message } from "@/components/chat/ChatContainer";

// ── Types ────────────────────────────────────────────────────

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

// ── localStorage helpers ─────────────────────────────────────

const STORAGE_KEY = "nmgpt_conversations";
const ACTIVE_KEY = "nmgpt_active_id";
const MAX_CONVS = 20;

function loadConversations(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function makeConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "New Chat",
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
}

// ── Component ────────────────────────────────────────────────

export default function ChatLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");

  // Load from localStorage on mount
  useEffect(() => {
    const saved = loadConversations();
    const savedActiveId = localStorage.getItem(ACTIVE_KEY) ?? "";
    if (saved.length === 0) {
      const conv = makeConversation();
      setConversations([conv]);
      setActiveId(conv.id);
    } else {
      setConversations(saved);
      const validId = saved.find((c) => c.id === savedActiveId)
        ? savedActiveId
        : saved[0].id;
      setActiveId(validId);
    }
  }, []);

  // Persist conversations to localStorage
  useEffect(() => {
    if (conversations.length === 0) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  // Persist active ID
  useEffect(() => {
    if (activeId) localStorage.setItem(ACTIVE_KEY, activeId);
  }, [activeId]);

  const activeConv = conversations.find((c) => c.id === activeId);
  const activeMessages = activeConv?.messages ?? [];

  // Called by ChatContainer whenever messages change
  const handleMessagesChange = useCallback(
    (update: React.SetStateAction<Message[]>) => {
      setConversations((convs) => {
        const conv = convs.find((c) => c.id === activeId);
        if (!conv) return convs;
        const newMessages =
          typeof update === "function" ? update(conv.messages) : update;
        const firstUserMsg = newMessages.find((m) => m.role === "user");
        const title = firstUserMsg
          ? firstUserMsg.content.slice(0, 40) +
            (firstUserMsg.content.length > 40 ? "…" : "")
          : conv.title;
        return convs.map((c) =>
          c.id === activeId
            ? { ...c, messages: newMessages, title, updatedAt: Date.now() }
            : c
        );
      });
    },
    [activeId]
  );

  const handleNewChat = useCallback(() => {
    const conv = makeConversation();
    setConversations((prev) => [conv, ...prev].slice(0, MAX_CONVS));
    setActiveId(conv.id);
    setIsSidebarOpen(false);
  }, []);

  const handleSelectConversation = useCallback((id: string) => {
    setActiveId(id);
    setIsSidebarOpen(false);
  }, []);

  const convTitle = activeConv?.title ?? "New Chat";

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden text-foreground">

      {/* Sidebar Overlay (Mobile) */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        onNewChat={handleNewChat}
        conversations={conversations}
        activeId={activeId}
        onSelectConversation={handleSelectConversation}
      />

      {/* Main area */}
      <main className="flex-1 flex flex-col min-w-0 relative overflow-hidden">

        {/* Top header bar */}
        <header className="shrink-0 h-12 border-b border-border flex items-center px-4 gap-3 bg-background/80 backdrop-blur-sm">
          {/* Mobile menu button */}
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-1.5 rounded-lg hover:bg-surface border border-transparent hover:border-border transition-all duration-200 md:hidden"
            aria-label="Toggle Menu"
          >
            {isSidebarOpen ? (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>

          {/* Center: breadcrumb title (desktop) */}
          <div className="hidden md:flex items-center gap-2 text-sm">
            <span className="text-muted font-medium">NM-GPT</span>
            <svg className="w-3.5 h-3.5 text-muted/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            <span className="text-foreground/80 font-medium truncate max-w-xs">{convTitle}</span>
          </div>

          {/* Mobile: just logo text */}
          <span className="text-sm font-bold text-foreground md:hidden">NM-GPT</span>

          {/* Right: status badge */}
          <div className="ml-auto flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] font-semibold text-muted uppercase tracking-widest hidden sm:block">Live</span>
          </div>
        </header>

        {/* Chat container — key remounts it when switching conversations */}
        <div className="flex-1 flex flex-col min-h-0 ambient-glow">
          <ChatContainer
            key={activeId}
            messages={activeMessages}
            onMessagesChange={handleMessagesChange}
          />
        </div>
      </main>
    </div>
  );
}
