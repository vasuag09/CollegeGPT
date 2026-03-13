"use client";

import { motion } from "framer-motion";

export default function Hero() {
  return (
    <section id="home" className="relative min-h-screen hero-gradient flex items-center pt-20">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 w-full">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left: Copy */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/5 border border-primary/10 text-xs font-medium text-primary mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              Powered by AI
            </div>

            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.1] mb-6">
              <span className="gradient-text">Nmims-GPT</span>
            </h1>

            <p className="text-lg sm:text-xl text-muted leading-relaxed max-w-lg mb-10">
              An AI assistant that helps students instantly find policies, rules,
              and academic information from the Student Resource Book.
            </p>

            <div className="flex flex-col sm:flex-row gap-4">
              <a
                href="/chat"
                className="btn-primary text-white font-medium px-8 py-3.5 rounded-full text-center"
              >
                Try Demo
              </a>
              <a
                href="#about"
                className="border border-gray-800 text-gray-300 font-medium px-8 py-3.5 rounded-full text-center hover:bg-gray-800 transition-colors duration-200"
              >
                Learn More
              </a>
            </div>
          </motion.div>

          {/* Right: Chat mockup */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
            className="animate-float"
          >
            <div className="glass-card rounded-2xl p-6 shadow-lg max-w-md mx-auto lg:mx-0 lg:ml-auto">
              {/* Window controls */}
              <div className="flex items-center gap-2 mb-5">
                <div className="w-3 h-3 rounded-full bg-red-500/80" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                <div className="w-3 h-3 rounded-full bg-green-500/80" />
                <span className="ml-3 text-xs text-gray-500 font-medium tracking-wider">NM-GPT</span>
              </div>

              {/* Messages */}
              <div className="space-y-4">
                <div className="flex justify-end">
                  <div className="chat-bubble-user px-4 py-3 rounded-2xl rounded-br-md max-w-[85%] shadow-sm">
                    <p className="text-sm">What is the minimum attendance requirement?</p>
                  </div>
                </div>

                <div className="flex justify-start">
                  <div className="chat-bubble-ai px-4 py-3 rounded-2xl rounded-bl-md max-w-[85%] shadow-sm">
                    <p className="text-sm text-gray-200 leading-relaxed">
                      Students must maintain a minimum of{" "}
                      <strong className="text-white">75% attendance</strong> in each course.
                    </p>
                    <div className="flex items-center gap-1.5 mt-3">
                      <div className="w-3.5 h-3.5 rounded-full bg-primary/20 flex items-center justify-center">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                      </div>
                      <p className="text-[10px] text-primary/90 uppercase tracking-wider font-bold">
                        Source: SRB Page 32
                      </p>
                    </div>
                  </div>
                </div>

                {/* Typing indicator */}
                <div className="flex items-center gap-1.5 px-4 py-2">
                  <div className="w-1.5 h-1.5 rounded-full typing-dot" />
                  <div className="w-1.5 h-1.5 rounded-full typing-dot" />
                  <div className="w-1.5 h-1.5 rounded-full typing-dot" />
                </div>
              </div>

              {/* Input mock */}
              <div className="mt-5 flex items-center gap-2 bg-gray-900/50 rounded-xl px-4 py-3 border border-gray-800/80">
                <span className="text-sm text-gray-500 flex-1">Ask anything about the SRB...</span>
                <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                  <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
