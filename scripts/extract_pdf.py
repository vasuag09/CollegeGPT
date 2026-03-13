#!/usr/bin/env python3
from __future__ import annotations

"""
CollegeGPT – PDF Text Extraction

Extracts text from the SRB PDF page-by-page using PyMuPDF,
preserving page numbers in metadata.

Usage:
    python scripts/extract_pdf.py

Output:
    data/chunks.jsonl is NOT produced here — this script outputs
    an intermediate JSON file (data/pages.json) that chunk_documents.py
    consumes.
"""

import json
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # PyMuPDF

from backend.config import SRB_PDF_PATH, DATA_DIR


def extract_pages(pdf_path: Path) -> list[dict]:
    """Extract text from every page of the PDF.

    Returns a list of dicts:
      {"page_number": int, "text": str}
    """
    doc = fitz.open(str(pdf_path))
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():  # skip blank pages
            pages.append({
                "page_number": page_num + 1,  # 1-indexed
                "text": text.strip(),
            })
    doc.close()
    return pages


def main():
    if not SRB_PDF_PATH.exists():
        print(f"❌ PDF not found at: {SRB_PDF_PATH}")
        sys.exit(1)

    print(f"📄 Extracting text from: {SRB_PDF_PATH.name}")
    pages = extract_pages(SRB_PDF_PATH)
    print(f"✅ Extracted {len(pages)} pages with text")

    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "pages.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved to: {output_path}")

    # Print a preview of the first page
    if pages:
        preview = pages[0]["text"][:300]
        print(f"\n── Page 1 Preview ──\n{preview}…")


if __name__ == "__main__":
    main()
