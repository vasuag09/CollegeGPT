#!/usr/bin/env python3
from __future__ import annotations

"""
NM-GPT – PDF Text Extraction

Extracts text from all PDFs in the pdfs/ directory page-by-page using PyMuPDF,
preserving page numbers and source document name in metadata.

Usage:
    python scripts/extract_pdf.py

Output:
    data/pages.json  — consumed by chunk_documents.py
"""

import json
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # PyMuPDF

from backend.config import DOCS_DIR, DATA_DIR


def extract_pages(pdf_path: Path) -> list[dict]:
    """Extract text from every page of a PDF.

    Returns a list of dicts:
      {"page_number": int, "text": str, "source_doc": str}
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
                "source_doc": pdf_path.stem,  # filename without extension
            })
    doc.close()
    return pages


def extract_txt(txt_path: Path) -> list[dict]:
    """Read a plain text file as a single page."""
    text = txt_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [{
        "page_number": 1,
        "text": text,
        "source_doc": txt_path.stem,
    }]


def main():
    if not DOCS_DIR.exists():
        print(f"❌ pdfs/ directory not found at: {DOCS_DIR}")
        print("   Create it and place your PDF files inside.")
        sys.exit(1)

    pdf_files = sorted(DOCS_DIR.glob("*.pdf"))
    txt_files = sorted(DOCS_DIR.glob("*.txt"))
    all_files = pdf_files + txt_files

    if not all_files:
        print(f"❌ No PDF or TXT files found in: {DOCS_DIR}")
        sys.exit(1)

    print(f"📂 Found {len(pdf_files)} PDF(s) and {len(txt_files)} TXT(s) in {DOCS_DIR.name}/")
    for f in all_files:
        print(f"   • {f.name}")

    all_pages = []
    for pdf_path in pdf_files:
        print(f"\n📄 Extracting: {pdf_path.name}")
        pages = extract_pages(pdf_path)
        print(f"   ✅ {len(pages)} pages extracted")
        all_pages.extend(pages)

    for txt_path in txt_files:
        print(f"\n📝 Reading: {txt_path.name}")
        pages = extract_txt(txt_path)
        print(f"   ✅ {len(pages)} page(s) loaded")
        all_pages.extend(pages)

    print(f"\n📊 Total pages across all documents: {len(all_pages)}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "pages.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_pages, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved to: {output_path}")


if __name__ == "__main__":
    main()
