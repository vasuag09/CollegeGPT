"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import ChatContainer from "@/components/chat/ChatContainer";

export default function ChatLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

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
      <Sidebar isOpen={isSidebarOpen} onToggle={() => setIsSidebarOpen(!isSidebarOpen)} />

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
            <span className="text-foreground/80 font-medium">New Chat</span>
          </div>

          {/* Mobile: just logo text */}
          <span className="text-sm font-bold text-foreground md:hidden">NM-GPT</span>

          {/* Right: status badge */}
          <div className="ml-auto flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] font-semibold text-muted uppercase tracking-widest hidden sm:block">Live</span>
          </div>
        </header>

        {/* Chat container */}
        <div className="flex-1 flex flex-col min-h-0 ambient-glow">
          <ChatContainer />
        </div>
      </main>
    </div>
  );
}
