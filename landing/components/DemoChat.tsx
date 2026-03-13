"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";

interface Message {
  role: "user" | "assistant";
  content: string;
  citation?: string;
}

const predefinedResponses: Record<string, { answer: string; citation: string }> = {
  attendance: {
    answer:
      "Students must maintain a minimum of 75% attendance in each course. Failure to meet this requirement may result in being debarred from examinations.",
    citation: "SRB Page 32",
  },
  exam: {
    answer:
      "Students can apply for revaluation within 7 days of result declaration by submitting a written application to the examination department along with the prescribed fee.",
    citation: "SRB Page 48",
  },
  revaluation: {
    answer:
      "Students can apply for revaluation within 7 days of result declaration by submitting a written application to the examination department along with the prescribed fee.",
    citation: "SRB Page 48",
  },
  illness: {
    answer:
      "If a student misses an exam due to illness, they must submit a medical certificate within 3 working days to the examination department. An alternative exam may be arranged at the discretion of the department.",
    citation: "SRB Page 51",
  },
  default: {
    answer:
      "I could not find this specific information in the Student Resource Book. Please try rephrasing your question or contact the administration office for assistance.",
    citation: "",
  },
};

function getResponse(query: string): { answer: string; citation: string } {
  const q = query.toLowerCase();
  if (q.includes("attendance")) return predefinedResponses.attendance;
  if (q.includes("revaluation") || q.includes("reval")) return predefinedResponses.revaluation;
  if (q.includes("exam")) return predefinedResponses.exam;
  if (q.includes("illness") || q.includes("sick") || q.includes("miss")) return predefinedResponses.illness;
  return predefinedResponses.default;
}

const initialMessages: Message[] = [
  {
    role: "assistant",
    content:
      "Hello! I'm NM-GPT, your AI assistant for NMIMS policies. Ask me anything about the Student Resource Book.",
  },
];

const suggestions = [
  "What is the minimum attendance requirement?",
  "What are the exam revaluation rules?",
  "What if I miss an exam due to illness?",
];

export default function DemoChat() {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (text?: string) => {
    const query = text || input;
    if (!query.trim()) return;

    const userMessage: Message = { role: "user", content: query };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    setTimeout(() => {
      const response = getResponse(query);
      const aiMessage: Message = {
        role: "assistant",
        content: response.answer,
        citation: response.citation,
      };
      setMessages((prev) => [...prev, aiMessage]);
      setIsTyping(false);
    }, 1200);
  };

  return (
    <section id="demo" className="py-24 sm:py-32 bg-surface">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-4">
            Try <span className="gradient-text">NM-GPT</span>
          </h2>
          <p className="text-muted text-lg max-w-xl mx-auto">
            Experience the assistant. Try asking a question below.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="max-w-2xl mx-auto"
        >
          <div className="glass-card rounded-2xl shadow-lg overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-800/60 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold">NM-GPT</h3>
                <p className="text-xs text-muted">Demo Mode</p>
              </div>
              <div className="ml-auto flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-xs text-muted">Online</span>
              </div>
            </div>

            {/* Messages */}
            <div className="h-80 overflow-y-auto px-6 py-4 space-y-4">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                      msg.role === "user"
                        ? "chat-bubble-user rounded-br-md"
                        : "chat-bubble-ai rounded-bl-md"
                    }`}
                  >
                    <p className={`text-sm leading-relaxed ${msg.role === "user" ? "text-white" : "text-gray-200"}`}>
                      {msg.content}
                    </p>
                    {msg.citation && (
                      <div className="mt-2 pt-2 border-t border-gray-800/40">
                        <p className="text-[10px] font-bold text-primary uppercase tracking-wider">
                          Source: {msg.citation}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isTyping && (
                <div className="flex justify-start">
                  <div className="chat-bubble-ai px-4 py-3 rounded-2xl rounded-bl-md">
                    <div className="flex items-center gap-1.5">
                      <div className="w-1.5 h-1.5 rounded-full typing-dot" />
                      <div className="w-1.5 h-1.5 rounded-full typing-dot" />
                      <div className="w-1.5 h-1.5 rounded-full typing-dot" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Suggestions */}
            {messages.length <= 1 && (
              <div className="px-6 pb-3">
                <p className="text-xs text-muted mb-2">Try asking:</p>
                <div className="flex flex-wrap gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => handleSend(s)}
                      className="text-xs px-3 py-1.5 rounded-full border border-primary/20 text-primary hover:bg-primary/10 transition-colors duration-200"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Input */}
            <div className="px-6 py-4 border-t border-gray-800/60">
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="Ask about college policies..."
                  className="flex-1 text-sm px-4 py-3 rounded-xl bg-gray-900/50 border border-gray-800/80 text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/30 transition-all duration-200"
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim()}
                  className="btn-primary w-10 h-10 rounded-xl flex items-center justify-center disabled:opacity-40 disabled:transform-none disabled:shadow-none"
                >
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
