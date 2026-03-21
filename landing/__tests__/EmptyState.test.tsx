/**
 * Tests for landing/components/chat/EmptyState.tsx
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import EmptyState from "../components/chat/EmptyState";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, className, ...rest }: React.HTMLAttributes<HTMLDivElement> & { children?: React.ReactNode }) => (
      <div className={className} {...rest}>{children}</div>
    ),
    button: ({ children, onClick, className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children?: React.ReactNode }) => (
      <button onClick={onClick} className={className} {...rest}>{children}</button>
    ),
    p: ({ children, className, ...rest }: React.HTMLAttributes<HTMLParagraphElement> & { children?: React.ReactNode }) => (
      <p className={className} {...rest}>{children}</p>
    ),
  },
}));

describe("EmptyState", () => {
  let onSelectPrompt: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSelectPrompt = vi.fn();
  });

  // ── Rendering ──────────────────────────────────────────────

  it("renders the main heading", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    expect(screen.getByText(/Ask anything about/i)).toBeInTheDocument();
    expect(screen.getByText("NMIMS")).toBeInTheDocument();
  });

  it("renders all 6 suggestion cards", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    const cards = screen.getAllByRole("button");
    expect(cards).toHaveLength(6);
  });

  it("renders Attendance Policy card", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    expect(screen.getByText("Attendance Policy")).toBeInTheDocument();
  });

  it("renders Exam Schedule card", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    expect(screen.getByText("Exam Schedule")).toBeInTheDocument();
  });

  it("renders UFM Consequences card", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    expect(screen.getByText("UFM Consequences")).toBeInTheDocument();
  });

  it("renders TEE Exam Rules card", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    expect(screen.getByText("TEE Exam Rules")).toBeInTheDocument();
  });

  it("renders Code of Conduct card", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    // The title appears as h3, so query by role to disambiguate from source badge
    const headings = screen.getAllByText("Code of Conduct");
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  it("renders Grievance Process card", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    expect(screen.getByText("Grievance Process")).toBeInTheDocument();
  });

  it("renders source badges", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    expect(screen.getAllByText("SRB").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Academic Calendar")).toBeInTheDocument();
    expect(screen.getByText("UFM Policy")).toBeInTheDocument();
  });

  it("shows the footer hint about official documents", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    expect(screen.getByText(/Powered by 6 official NMIMS documents/i)).toBeInTheDocument();
  });

  // ── Interactions ───────────────────────────────────────────

  it("calls onSelectPrompt when Attendance Policy card is clicked", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    fireEvent.click(screen.getByText("Attendance Policy").closest("button")!);
    expect(onSelectPrompt).toHaveBeenCalledTimes(1);
    expect(onSelectPrompt).toHaveBeenCalledWith(
      "What is the minimum attendance requirement for NMIMS students?"
    );
  });

  it("calls onSelectPrompt when Exam Schedule card is clicked", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    fireEvent.click(screen.getByText("Exam Schedule").closest("button")!);
    expect(onSelectPrompt).toHaveBeenCalledWith(
      "When are the Term End Exams for Semester I and Semester II?"
    );
  });

  it("calls onSelectPrompt when UFM Consequences card is clicked", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    fireEvent.click(screen.getByText("UFM Consequences").closest("button")!);
    expect(onSelectPrompt).toHaveBeenCalledWith(
      "What are the penalties for using unfair means during examinations?"
    );
  });

  it("calls onSelectPrompt when Code of Conduct card is clicked", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    // Multiple elements with "Code of Conduct" (title + source badge); use the first
    const elements = screen.getAllByText("Code of Conduct");
    const btn = elements[0].closest("button")!;
    fireEvent.click(btn);
    expect(onSelectPrompt).toHaveBeenCalledWith(
      "What is the student code of conduct during university examinations?"
    );
  });

  it("each card click passes the full prompt text", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => fireEvent.click(btn));
    // Every click should pass a non-empty string
    onSelectPrompt.mock.calls.forEach(([prompt]) => {
      expect(typeof prompt).toBe("string");
      expect(prompt.length).toBeGreaterThan(0);
    });
  });

  it("calls onSelectPrompt once per card click", () => {
    render(<EmptyState onSelectPrompt={onSelectPrompt} />);
    fireEvent.click(screen.getByText("Attendance Policy").closest("button")!);
    expect(onSelectPrompt).toHaveBeenCalledTimes(1);
  });
});
