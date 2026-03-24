"use client";

import Image from "next/image";
import { useState } from "react";

interface SidebarProps {
  onNewChat?: () => void;
  isOpen?: boolean;
  onToggle?: () => void;
}

const knowledgeBase = [
  { label: "Student Resource Book", short: "SRB", icon: "📘" },
  { label: "Academic Calendar", short: "2025–26", icon: "📅" },
  { label: "TEE Exam Instructions", short: "Exams", icon: "📝" },
  { label: "Code of Conduct", short: "Conduct", icon: "⚖️" },
  { label: "UFM Offence Penalties", short: "UFM", icon: "🚨" },
  { label: "Exam Instructions", short: "Rules", icon: "📋" },
];


export default function Sidebar({ onNewChat, isOpen = true }: SidebarProps) {
  const [kbExpanded, setKbExpanded] = useState(true);

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-50 w-56 sm:w-64 flex flex-col bg-surface border-r border-border transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${
        isOpen ? "translate-x-0" : "-translate-x-full"
      }`}
    >
      {/* Amber accent top bar */}
      <div className="h-0.5 w-full bg-gradient-to-r from-primary via-accent to-transparent shrink-0" />

      <div className="flex flex-col h-full overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-5 shrink-0">
          <div className="relative">
            <div className="w-8 h-8 rounded-lg overflow-hidden ring-1 ring-primary/30 pulse-glow">
              <Image
                src="/logo.jpg"
                alt="NMIMS"
                width={32}
                height={32}
                className="object-cover"
              />
            </div>
          </div>
          <div>
            <p className="text-sm font-bold tracking-tight text-foreground leading-none">NM-GPT</p>
            <p className="text-[10px] text-muted mt-0.5 tracking-wide">Campus AI Assistant</p>
          </div>
        </div>

        {/* New Chat */}
        <div className="px-4 shrink-0 mb-4">
          <button
            onClick={onNewChat || (() => window.location.reload())}
            className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-primary/10 hover:bg-primary/20 border border-primary/25 hover:border-primary/50 text-primary rounded-xl transition-all duration-200 font-semibold text-sm group"
          >
            <svg className="w-4 h-4 group-hover:rotate-90 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Chat
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-3 space-y-4 pb-4">

          {/* Knowledge Base */}
          <div>
            <button
              onClick={() => setKbExpanded(!kbExpanded)}
              className="flex items-center justify-between w-full px-2 py-1.5 text-[10px] font-bold text-muted uppercase tracking-widest hover:text-foreground transition-colors group"
            >
              <div className="flex items-center gap-1.5">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 10V7" />
                </svg>
                Knowledge Base
              </div>
              <svg
                className={`w-3 h-3 transition-transform duration-200 ${kbExpanded ? "rotate-180" : ""}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {kbExpanded && (
              <div className="mt-1 space-y-0.5">
                {knowledgeBase.map((doc) => (
                  <div
                    key={doc.label}
                    className="kb-item flex items-center gap-2.5 px-2 py-2 rounded-lg cursor-default"
                  >
                    <span className="text-sm w-5 text-center shrink-0">{doc.icon}</span>
                    <span className="text-[12px] text-muted truncate leading-tight">{doc.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Footer */}
        <div className="shrink-0 px-4 py-4 border-t border-border">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
              Beta
            </span>
            <span className="text-[10px] text-muted">MPSTME · NMIMS</span>
          </div>
          <p className="text-[10px] text-muted/60 leading-relaxed">
            By Vasu Agrawal &amp; Vanisha Sharma
          </p>
        </div>
      </div>
    </aside>
  );
}
