"use client";

import Image from "next/image";

export default function Footer() {
  return (
    <footer id="contact" className="py-16 border-t border-gray-800/60">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex flex-col items-center text-center">
          {/* Logo and name */}
          <div className="flex items-center gap-3 mb-6">
            <Image
              src="/logo.jpg"
              alt="NMIMS Logo"
              width={36}
              height={36}
              className="rounded-lg"
            />
            <div className="text-left">
              <p className="text-sm font-semibold text-gray-50">
                SVKM&apos;s NMIMS
              </p>
              <p className="text-xs text-muted">NM-GPT</p>
            </div>
          </div>

          {/* Divider */}
          <div className="w-16 h-px bg-gray-800 mb-6" />

          {/* Credits */}
          <p className="text-sm text-muted">
            Built by{" "}
            <span className="font-medium text-gray-300">Vasu Agrawal</span>
            {" & "}
            <span className="font-medium text-gray-300">Vanisha Sharma</span>
          </p>

          {/* Copyright */}
          <p className="text-xs text-gray-500 mt-3">
            &copy; {new Date().getFullYear()} SVKM&apos;s NMIMS. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
