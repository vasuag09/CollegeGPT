"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

interface SidebarProps {
  onNewChat?: () => void;
  isOpen?: boolean;
  onToggle?: () => void;
}

export default function Sidebar({ onNewChat, isOpen = true, onToggle }: SidebarProps) {
  const [conversations] = useState([
    { id: "1", title: "Attendance Requirements", date: "Today" },
    { id: "2", title: "Exam Rules 2024", date: "Yesterday" },
    { id: "3", title: "Grievance Procedure", date: "2 days ago" },
  ]);

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-50 w-64 bg-surface border-r border-border transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
    >
      <div className="flex flex-col h-full p-4">
        {/* Header: Logo + Title */}
        <div className="flex items-center gap-3 mb-8 px-2">
          <Image
            src="/logo.jpg"
            alt="NMIMS Logo"
            width={32}
            height={32}
            className="rounded-lg shadow-sm"
          />
          <span className="text-lg font-bold tracking-tight text-foreground">
            NM-GPT
          </span>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNewChat || (() => window.location.reload())}
          className="flex items-center gap-2 w-full px-4 py-3 mb-6 bg-primary hover:bg-primary-dark text-white rounded-xl transition-all duration-200 shadow-lg shadow-primary/20 font-medium"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>

        {/* Conversation History */}
        <div className="flex-1 overflow-y-auto space-y-1 mb-4 custom-scrollbar">
          <div className="px-2 mb-2 text-xs font-semibold text-muted uppercase tracking-wider">
            History
          </div>
          {conversations.map((chat) => (
            <button
              key={chat.id}
              className="flex items-center gap-3 w-full px-3 py-2.5 text-sm text-muted hover:text-foreground hover:bg-bubble-ai rounded-lg transition-all duration-200 group text-left"
            >
              <svg
                className="w-4 h-4 text-muted group-hover:text-primary transition-colors"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                />
              </svg>
              <span className="truncate">{chat.title}</span>
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-border mt-auto">
          <div className="flex items-center justify-between px-2 py-2">
            <span className="text-[10px] font-bold tracking-widest uppercase px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-sm">
              Prototype v2.0
            </span>
            <span className="text-xs text-muted font-medium">NMIMS SRB</span>
          </div>
          <div className="px-2 pb-2 mt-1">
            <p className="text-[10px] text-muted-foreground/60 font-medium">
              Created by Vasu Agrawal & Vanisha Sharma
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
