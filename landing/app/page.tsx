import type { Metadata } from "next";
import ChatLayout from "@/components/chat/ChatLayout";

export const metadata: Metadata = {
  title: "NM-GPT | Chat",
  description:
    "Ask NM-GPT about NMIMS policies, rules, and academic information from the Student Resource Book.",
};

export default function HomePage() {
  return <ChatLayout />;
}
