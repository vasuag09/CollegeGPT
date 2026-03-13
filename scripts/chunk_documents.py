#!/usr/bin/env python3
from __future__ import annotations

"""
NM-GPT – Document Chunking

Reads the extracted pages (data/pages.json) and splits them into
semantic chunks with metadata, outputting data/chunks.jsonl.

Each chunk record contains:
  chunk_id   – unique identifier
  text       – chunk text
  source     – source document name
  page_start – first page the chunk draws from
  page_end   – last page the chunk draws from

Usage:
    python scripts/chunk_documents.py
"""

import json
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP


SOURCE_NAME = "Student Resource Book (SRB) A.Y. 2025-26"


def load_pages(pages_path: Path) -> list[dict]:
    """Load extracted pages from JSON."""
    with open(pages_path, "r", encoding="utf-8") as f:
        return json.load(f)


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Split page texts into overlapping chunks, tracking page ranges."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    chunk_id = 0

    for page in pages:
        page_num = page["page_number"]
        text = page["text"]

        # Split this page's text
        page_chunks = splitter.split_text(text)

        for chunk_text in page_chunks:
            chunks.append({
                "chunk_id": f"chunk_{chunk_id:04d}",
                "text": chunk_text,
                "source": SOURCE_NAME,
                "page_start": page_num,
                "page_end": page_num,
            })
            chunk_id += 1

    return chunks


def merge_cross_page_chunks(chunks: list[dict]) -> list[dict]:
    """
    Post-process: if the last chunk of page N and first chunk of page N+1
    are very short, merge them to avoid tiny stubs.
    (Simple heuristic — keeps chunk quality high.)
    """
    MIN_CHUNK_LENGTH = 100
    merged = []
    skip_next = False

    for i, chunk in enumerate(chunks):
        if skip_next:
            skip_next = False
            continue

        if (
            i + 1 < len(chunks)
            and len(chunk["text"]) < MIN_CHUNK_LENGTH
            and chunk["page_end"] + 1 == chunks[i + 1]["page_start"]
        ):
            # Merge with next chunk
            merged_chunk = {
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"] + "\n" + chunks[i + 1]["text"],
                "source": chunk["source"],
                "page_start": chunk["page_start"],
                "page_end": chunks[i + 1]["page_end"],
            }
            merged.append(merged_chunk)
            skip_next = True
        else:
            merged.append(chunk)

    return merged


def main():
    pages_path = DATA_DIR / "pages.json"
    if not pages_path.exists():
        print("❌ pages.json not found. Run extract_pdf.py first.")
        sys.exit(1)

    print("📖 Loading extracted pages…")
    pages = load_pages(pages_path)
    print(f"   {len(pages)} pages loaded")

    print("✂️  Chunking text…")
    chunks = chunk_pages(pages)
    print(f"   {len(chunks)} raw chunks created")

    print("🔗 Merging short cross-page chunks…")
    chunks = merge_cross_page_chunks(chunks)
    print(f"   {len(chunks)} final chunks")

    # Re-index chunk IDs after merging
    for i, chunk in enumerate(chunks):
        chunk["chunk_id"] = f"chunk_{i:04d}"

    # Write JSONL
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "chunks.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"💾 Saved {len(chunks)} chunks to: {output_path}")

    # Show sample
    if chunks:
        sample = chunks[0]
        print(f"\n── Sample Chunk ──")
        print(f"   ID:    {sample['chunk_id']}")
        print(f"   Pages: {sample['page_start']}–{sample['page_end']}")
        print(f"   Text:  {sample['text'][:200]}…")


if __name__ == "__main__":
    main()
