import type { Metadata } from "next";
import ChatLayout from "@/components/chat/ChatLayout";

export const metadata: Metadata = {
  title: "CollegeGPT | Chat",
  description:
    "Ask CollegeGPT about NMIMS policies, rules, and academic information from the Student Resource Book.",
};

export default function ChatPage() {
  return <ChatLayout />;
}
