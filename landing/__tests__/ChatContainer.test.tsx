/**
 * Tests for landing/components/chat/ChatContainer.tsx
 */

import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import ChatContainer from "../components/chat/ChatContainer";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, className, ...rest }: React.HTMLAttributes<HTMLDivElement> & { children?: React.ReactNode }) => (
      <div className={className} {...rest}>{children}</div>
    ),
    button: ({ children, onClick, disabled, className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children?: React.ReactNode }) => (
      <button onClick={onClick} disabled={disabled} className={className} {...rest}>{children}</button>
    ),
    p: ({ children, ...rest }: React.HTMLAttributes<HTMLParagraphElement> & { children?: React.ReactNode }) => <p {...rest}>{children}</p>,
    span: ({ children, ...rest }: React.HTMLAttributes<HTMLSpanElement> & { children?: React.ReactNode }) => <span {...rest}>{children}</span>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock react-markdown
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}));

vi.mock("remark-gfm", () => ({ default: () => {} }));

// ── SSE stream helpers ────────────────────────────────────

function makeSSEStream(events: object[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      }
      controller.close();
    },
  });
}

function mockFetchOk(events: object[]) {
  return vi.fn().mockResolvedValue({
    ok: true,
    body: makeSSEStream(events),
    json: () => Promise.resolve({}),
  });
}

function mockFetchError(status: number, detail: string) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: () => Promise.resolve({ detail }),
    body: null,
  });
}

function mockFetchNetworkError() {
  return vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
}

// ── Tests ─────────────────────────────────────────────────

describe("ChatContainer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Initial render ─────────────────────────────────────────

  it("shows EmptyState on initial render", () => {
    render(<ChatContainer />);
    expect(screen.getByText(/Ask anything about/i)).toBeInTheDocument();
  });

  it("shows the chat input on initial render", () => {
    render(<ChatContainer />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  // ── Sending a message ──────────────────────────────────────

  it("adds user message to the chat when sent", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchOk([
        { type: "token", content: "Hello" },
        { type: "done" },
      ])
    );

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "What is the attendance policy?" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText("What is the attendance policy?")).toBeInTheDocument();
    });
  });

  it("hides EmptyState once a message is sent", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchOk([{ type: "token", content: "answer" }, { type: "done" }])
    );

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "test question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(screen.queryByText(/Ask anything about/i)).not.toBeInTheDocument();
    });
  });

  it("clears the input field after sending", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchOk([{ type: "token", content: "answer" }, { type: "done" }])
    );

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "test question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(textarea).toHaveValue("");
    });
  });

  it("calls fetch with the correct URL and payload", async () => {
    const mockFetch = mockFetchOk([{ type: "done" }]);
    vi.stubGlobal("fetch", mockFetch);

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "my question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/query/stream");
    const body = JSON.parse(options.body);
    expect(body.question).toBe("my question");
    expect(body.top_k).toBe(5);
  });

  // ── SSE token streaming ────────────────────────────────────

  it("displays streamed tokens in the AI message", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchOk([
        { type: "token", content: "Attendance" },
        { type: "token", content: " is 75%." },
        { type: "done" },
      ])
    );

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "attendance?" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText("Attendance is 75%.")).toBeInTheDocument();
    });
  });

  it("removes streaming flag after done event", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchOk([
        { type: "token", content: "answer" },
        { type: "done" },
      ])
    );

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    // After done, input should be re-enabled
    await waitFor(() => {
      expect(screen.getByRole("textbox")).not.toBeDisabled();
    });
  });

  // ── Error handling ─────────────────────────────────────────

  it("shows error message when server returns non-ok response", async () => {
    vi.stubGlobal("fetch", mockFetchError(503, "Index not found"));

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText("Index not found")).toBeInTheDocument();
    });
  });

  it("shows connection error message on network failure", async () => {
    vi.stubGlobal("fetch", mockFetchNetworkError());

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText(/Unable to connect to the NM-GPT server/i)).toBeInTheDocument();
    });
  });

  it("shows error event message from SSE stream", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchOk([
        { type: "error", message: "Gemini API is unavailable" },
      ])
    );

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText("Gemini API is unavailable")).toBeInTheDocument();
    });
  });

  // ── Input disabled during loading ──────────────────────────

  it("disables input while request is in flight", async () => {
    // Never-resolving fetch to keep loading state
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(textarea).toBeDisabled();
    });
  });

  // ── Selecting a suggestion ─────────────────────────────────

  it("sends message when a suggestion card is clicked from EmptyState", async () => {
    const mockFetch = mockFetchOk([{ type: "done" }]);
    vi.stubGlobal("fetch", mockFetch);

    render(<ChatContainer />);
    fireEvent.click(screen.getByText("Attendance Policy").closest("button")!);

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.question).toBe("What is the minimum attendance requirement for NMIMS students?");
  });

  // ── Retry ──────────────────────────────────────────────────

  it("retry button calls sendMessage with the last user question", async () => {
    // First call fails, second succeeds
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: "Server error" }),
        body: null,
      })
      .mockResolvedValueOnce({
        ok: true,
        body: makeSSEStream([{ type: "token", content: "retry answer" }, { type: "done" }]),
        json: () => Promise.resolve({}),
      });

    vi.stubGlobal("fetch", mockFetch);

    render(<ChatContainer />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "retry question" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText(/try again/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/try again/i));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2);
      const body = JSON.parse(mockFetch.mock.calls[1][1].body);
      expect(body.question).toBe("retry question");
    });
  });
});
