/**
 * Tests for landing/components/chat/MessageBubble.tsx
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import MessageBubble, { TypingIndicator } from "../components/chat/MessageBubble";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, className, ...rest }: React.HTMLAttributes<HTMLDivElement> & { children?: React.ReactNode }) => (
      <div className={className} {...rest}>{children}</div>
    ),
    span: ({ children, ...rest }: React.HTMLAttributes<HTMLSpanElement> & { children?: React.ReactNode }) => <span {...rest}>{children}</span>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock CitationBlock (tested separately)
vi.mock("../components/chat/CitationBlock", () => ({
  default: ({ citations }: { citations: unknown[] }) => (
    <div data-testid="citation-block">Citations: {citations.length}</div>
  ),
}));

// Mock react-markdown
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}));

// Mock remark-gfm
vi.mock("remark-gfm", () => ({ default: () => {} }));

const SAMPLE_CITATIONS = [
  {
    text: "Attendance must be at least 75%.",
    page_start: 10,
    page_end: 10,
    chunk_id: "c1",
    source: "SRB",
  },
];

describe("MessageBubble", () => {
  // ── User messages ──────────────────────────────────────────

  it("renders user message content", () => {
    render(<MessageBubble role="user" content="What is the attendance policy?" />);
    expect(screen.getByText("What is the attendance policy?")).toBeInTheDocument();
  });

  it("renders user avatar for user messages", () => {
    const { container } = render(<MessageBubble role="user" content="hello" />);
    // User bubble uses justify-end, AI uses justify-start
    expect(container.querySelector(".justify-end")).toBeInTheDocument();
  });

  it("does not show citation block for user messages", () => {
    render(
      <MessageBubble
        role="user"
        content="hello"
        citations={SAMPLE_CITATIONS}
        pages={[10]}
        confidence={0.9}
      />
    );
    expect(screen.queryByTestId("citation-block")).not.toBeInTheDocument();
  });

  // ── Assistant messages ─────────────────────────────────────

  it("renders assistant message content", () => {
    render(<MessageBubble role="assistant" content="The attendance policy is 75%." />);
    expect(screen.getByText("The attendance policy is 75%.")).toBeInTheDocument();
  });

  it("renders AI avatar for assistant messages", () => {
    const { container } = render(<MessageBubble role="assistant" content="answer" />);
    expect(container.querySelector(".justify-start")).toBeInTheDocument();
  });

  it("shows citation block when assistant has citations", () => {
    render(
      <MessageBubble
        role="assistant"
        content="Here is the answer."
        citations={SAMPLE_CITATIONS}
        pages={[10]}
        confidence={0.9}
      />
    );
    expect(screen.getByTestId("citation-block")).toBeInTheDocument();
  });

  it("does not show citation block when citations array is empty", () => {
    render(
      <MessageBubble
        role="assistant"
        content="Here is the answer."
        citations={[]}
        pages={[]}
        confidence={0.9}
      />
    );
    expect(screen.queryByTestId("citation-block")).not.toBeInTheDocument();
  });

  it("does not show citation block when citations are not provided", () => {
    render(<MessageBubble role="assistant" content="Here is the answer." />);
    expect(screen.queryByTestId("citation-block")).not.toBeInTheDocument();
  });

  // ── Error state ────────────────────────────────────────────

  it("renders error message content", () => {
    render(
      <MessageBubble
        role="assistant"
        content="Something went wrong."
        isError={true}
      />
    );
    expect(screen.getByText("Something went wrong.")).toBeInTheDocument();
  });

  it("does not show citation block for error messages", () => {
    render(
      <MessageBubble
        role="assistant"
        content="Error occurred"
        isError={true}
        citations={SAMPLE_CITATIONS}
        pages={[10]}
        confidence={0.9}
      />
    );
    expect(screen.queryByTestId("citation-block")).not.toBeInTheDocument();
  });

  it("shows retry button when isError and onRetry provided", () => {
    render(
      <MessageBubble
        role="assistant"
        content="Error"
        isError={true}
        onRetry={vi.fn()}
      />
    );
    expect(screen.getByText(/try again/i)).toBeInTheDocument();
  });

  it("does not show retry button when isError but no onRetry", () => {
    render(
      <MessageBubble role="assistant" content="Error" isError={true} />
    );
    expect(screen.queryByText(/try again/i)).not.toBeInTheDocument();
  });

  it("calls onRetry when retry button is clicked", () => {
    const onRetry = vi.fn();
    render(
      <MessageBubble
        role="assistant"
        content="Error"
        isError={true}
        onRetry={onRetry}
      />
    );
    fireEvent.click(screen.getByText(/try again/i));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

// ── TypingIndicator ────────────────────────────────────────

describe("TypingIndicator", () => {
  it("renders three typing dots", () => {
    const { container } = render(<TypingIndicator />);
    const dots = container.querySelectorAll(".typing-dot");
    expect(dots).toHaveLength(3);
  });

  it("is visible in the DOM", () => {
    const { container } = render(<TypingIndicator />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
