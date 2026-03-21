/**
 * Tests for landing/components/chat/ChatInput.tsx
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ChatInput from "../components/chat/ChatInput";

// Mock framer-motion to avoid animation issues in jsdom
vi.mock("framer-motion", () => ({
  motion: {
    button: ({ children, onClick, disabled, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children?: React.ReactNode }) => (
      <button onClick={onClick} disabled={disabled} {...rest}>
        {children}
      </button>
    ),
  },
}));

const DEFAULT_PROPS = {
  value: "",
  onChange: vi.fn(),
  onSend: vi.fn(),
  disabled: false,
};

describe("ChatInput", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Rendering ──────────────────────────────────────────────

  it("renders the textarea", () => {
    render(<ChatInput {...DEFAULT_PROPS} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("renders the send button", () => {
    render(<ChatInput {...DEFAULT_PROPS} />);
    expect(screen.getByRole("button", { name: /send message/i })).toBeInTheDocument();
  });

  it("shows character counter as 0/500 initially", () => {
    render(<ChatInput {...DEFAULT_PROPS} />);
    expect(screen.getByText("0/500")).toBeInTheDocument();
  });

  it("shows current character count", () => {
    render(<ChatInput {...DEFAULT_PROPS} value="hello" />);
    expect(screen.getByText("5/500")).toBeInTheDocument();
  });

  // ── onChange ───────────────────────────────────────────────

  it("calls onChange when user types", () => {
    const onChange = vi.fn();
    render(<ChatInput {...DEFAULT_PROPS} onChange={onChange} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "test input" } });
    expect(onChange).toHaveBeenCalledWith("test input");
  });

  // ── Send button disabled states ────────────────────────────

  it("send button is disabled when value is empty", () => {
    render(<ChatInput {...DEFAULT_PROPS} value="" />);
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("send button is disabled when value is only whitespace", () => {
    render(<ChatInput {...DEFAULT_PROPS} value="   " />);
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("send button is enabled when value has text", () => {
    render(<ChatInput {...DEFAULT_PROPS} value="hello" />);
    expect(screen.getByRole("button", { name: /send message/i })).not.toBeDisabled();
  });

  it("send button is disabled when component is disabled", () => {
    render(<ChatInput {...DEFAULT_PROPS} value="hello" disabled={true} />);
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("send button is disabled when message exceeds 500 chars", () => {
    render(<ChatInput {...DEFAULT_PROPS} value={"x".repeat(501)} />);
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("send button is enabled at exactly 500 chars", () => {
    render(<ChatInput {...DEFAULT_PROPS} value={"x".repeat(500)} />);
    expect(screen.getByRole("button", { name: /send message/i })).not.toBeDisabled();
  });

  // ── onSend ─────────────────────────────────────────────────

  it("calls onSend when send button is clicked", () => {
    const onSend = vi.fn();
    render(<ChatInput {...DEFAULT_PROPS} value="test question" onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("does not call onSend when button is disabled (empty value)", () => {
    const onSend = vi.fn();
    render(<ChatInput {...DEFAULT_PROPS} value="" onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    expect(onSend).not.toHaveBeenCalled();
  });

  // ── Enter key ──────────────────────────────────────────────

  it("calls onSend when Enter is pressed with text", () => {
    const onSend = vi.fn();
    render(<ChatInput {...DEFAULT_PROPS} value="valid question" onSend={onSend} />);
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", shiftKey: false });
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("does not call onSend on Shift+Enter", () => {
    const onSend = vi.fn();
    render(<ChatInput {...DEFAULT_PROPS} value="valid question" onSend={onSend} />);
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend on Enter when disabled", () => {
    const onSend = vi.fn();
    render(<ChatInput {...DEFAULT_PROPS} value="valid question" onSend={onSend} disabled={true} />);
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", shiftKey: false });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend on Enter when message is too long", () => {
    const onSend = vi.fn();
    render(<ChatInput {...DEFAULT_PROPS} value={"x".repeat(501)} onSend={onSend} />);
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", shiftKey: false });
    expect(onSend).not.toHaveBeenCalled();
  });

  // ── Character limit display ────────────────────────────────

  it("textarea is disabled when disabled prop is true", () => {
    render(<ChatInput {...DEFAULT_PROPS} disabled={true} />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });
});
