"use client";

import { motion } from "framer-motion";

const features = [
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
    title: "Natural Language Understanding",
    description: "Ask questions in plain English, just like talking to a person.",
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
    title: "Smart SRB Retrieval",
    description: "Automatically finds the most relevant sections from the Student Resource Book.",
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: "Accurate Answers",
    description: "Provides precise, factual answers grounded in official documentation.",
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
      </svg>
    ),
    title: "Official Citations",
    description: "Every answer includes page references so students can verify the source.",
  },
];

export default function SolutionSection() {
  return (
    <section className="py-24 sm:py-32">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left: Features */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mb-4">
              Meet <span className="gradient-text">NM-GPT</span>
            </h2>
            <p className="text-muted text-lg mb-10 max-w-md">
              Your intelligent assistant for navigating college policies instantly.
            </p>

            <div className="space-y-6">
              {features.map((feature) => (
                <div key={feature.title} className="flex gap-4">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
                    {feature.icon}
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm mb-1">{feature.title}</h3>
                    <p className="text-muted text-sm leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Right: Example conversation card */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.15 }}
          >
            <div className="glass-card rounded-2xl p-8 shadow-lg">
              <div className="flex items-center gap-2 mb-6">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-xs font-medium text-gray-400">Live Example</span>
              </div>

              {/* Student message */}
              <div className="mb-4">
                <p className="text-xs font-medium text-muted mb-2 uppercase tracking-wide">Student</p>
                <div className="chat-bubble-user px-5 py-3.5 rounded-2xl rounded-br-md inline-block">
                  <p className="text-sm">&ldquo;What is the attendance requirement?&rdquo;</p>
                </div>
              </div>

              {/* AI response */}
              <div>
                <p className="text-xs font-medium text-muted mb-2 uppercase tracking-wide">NM-GPT</p>
                <div className="chat-bubble-ai px-5 py-4 rounded-2xl rounded-bl-md">
                  <p className="text-sm text-gray-200 leading-relaxed">
                    &ldquo;Students must maintain a minimum of{" "}
                    <strong className="text-white">75% attendance</strong> in each course. Failure to meet
                    this requirement may result in being debarred from
                    examinations.&rdquo;
                  </p>
                  <div className="mt-3 pt-3 border-t border-gray-800/60">
                    <p className="text-xs font-semibold text-primary">
                      Source: SRB Page 32
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
