/**
 * Tests for landing/components/chat/CitationBlock.tsx
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import CitationBlock from "../components/chat/CitationBlock";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...rest }: React.HTMLAttributes<HTMLDivElement> & { children?: React.ReactNode }) => <div {...rest}>{children}</div>,
    span: ({ children, ...rest }: React.HTMLAttributes<HTMLSpanElement> & { children?: React.ReactNode }) => <span {...rest}>{children}</span>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const SAMPLE_CITATION = {
  text: "The minimum attendance requirement is 75% for all subjects.",
  page_start: 12,
  page_end: 12,
  chunk_id: "chunk_001",
  source: "Final SRB A.Y. 2025-26",
};

const SAMPLE_CITATIONS = [SAMPLE_CITATION];

describe("CitationBlock", () => {
  // ── Visibility ─────────────────────────────────────────────

  it("renders nothing when citations array is empty", () => {
    const { container } = render(
      <CitationBlock citations={[]} pages={[]} confidence={0.8} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders when citations are provided", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    expect(screen.getByText(/sources/i)).toBeInTheDocument();
  });

  // ── Page display ───────────────────────────────────────────

  it("shows page number pill", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    expect(screen.getByText("p.12")).toBeInTheDocument();
  });

  it("shows consecutive pages as a range", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[10, 11, 12]} confidence={0.8} />);
    expect(screen.getByText("p.10–12")).toBeInTheDocument();
  });

  it("shows non-consecutive pages as separate pills", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[5, 10]} confidence={0.8} />);
    expect(screen.getByText("p.5")).toBeInTheDocument();
    expect(screen.getByText("p.10")).toBeInTheDocument();
  });

  it("deduplicates repeated pages", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12, 12]} confidence={0.8} />);
    const pills = screen.getAllByText("p.12");
    expect(pills).toHaveLength(1);
  });

  // ── Source display ─────────────────────────────────────────

  it("shows source document name", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    expect(screen.getByText("Final SRB A.Y. 2025-26")).toBeInTheDocument();
  });

  it("deduplicates repeated source documents", () => {
    const duplicateSources = [
      SAMPLE_CITATION,
      { ...SAMPLE_CITATION, chunk_id: "chunk_002", page_start: 13 },
    ];
    render(<CitationBlock citations={duplicateSources} pages={[12, 13]} confidence={0.8} />);
    const sourceLabels = screen.getAllByText("Final SRB A.Y. 2025-26");
    expect(sourceLabels).toHaveLength(1);
  });

  it("handles citations without source gracefully", () => {
    const noCite = { ...SAMPLE_CITATION, source: undefined };
    render(<CitationBlock citations={[noCite]} pages={[12]} confidence={0.8} />);
    expect(screen.getByText(/sources/i)).toBeInTheDocument();
  });

  // ── Confidence display ─────────────────────────────────────

  it("displays confidence as a percentage", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.75} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("rounds confidence to nearest integer", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.856} />);
    expect(screen.getByText("86%")).toBeInTheDocument();
  });

  // ── Expand / collapse ──────────────────────────────────────

  it("shows toggle button with citation count", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    expect(screen.getByText(/view 1 source excerpt/i)).toBeInTheDocument();
  });

  it("shows plural for multiple citations", () => {
    const multipleCitations = [
      SAMPLE_CITATION,
      { ...SAMPLE_CITATION, chunk_id: "chunk_002" },
    ];
    render(<CitationBlock citations={multipleCitations} pages={[12]} confidence={0.8} />);
    expect(screen.getByText(/view 2 source excerpts/i)).toBeInTheDocument();
  });

  it("excerpts are hidden before expanding", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    expect(screen.queryByText(/minimum attendance requirement/i)).not.toBeInTheDocument();
  });

  it("shows excerpts after clicking toggle", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    fireEvent.click(screen.getByText(/view 1 source excerpt/i));
    expect(screen.getByText(/minimum attendance requirement/i)).toBeInTheDocument();
  });

  it("shows 'Hide excerpts' label when expanded", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    fireEvent.click(screen.getByText(/view 1 source excerpt/i));
    expect(screen.getByText(/hide excerpts/i)).toBeInTheDocument();
  });

  it("hides excerpts after collapsing", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    fireEvent.click(screen.getByText(/view 1 source excerpt/i));
    fireEvent.click(screen.getByText(/hide excerpts/i));
    expect(screen.queryByText(/minimum attendance requirement/i)).not.toBeInTheDocument();
  });

  it("shows source and page in expanded excerpt", () => {
    render(<CitationBlock citations={SAMPLE_CITATIONS} pages={[12]} confidence={0.8} />);
    fireEvent.click(screen.getByText(/view 1 source excerpt/i));
    // The excerpt header shows "source · Page N"
    expect(screen.getByText(/Final SRB A.Y. 2025-26.*Page 12/)).toBeInTheDocument();
  });
});
