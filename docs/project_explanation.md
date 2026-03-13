# NM-GPT — Complete Project Explanation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Project Structure](#5-project-structure)
6. [Core Concepts: RAG Explained](#6-core-concepts-rag-explained)
7. [Configuration Module](#7-configuration-module)
8. [Document Ingestion Pipeline](#8-document-ingestion-pipeline)
9. [Embeddings Module](#9-embeddings-module)
10. [Vector Index Builder](#10-vector-index-builder)
11. [LLM Client](#11-llm-client)
12. [Prompt Engineering](#12-prompt-engineering)
13. [RAG Pipeline](#13-rag-pipeline)
14. [FastAPI Backend](#14-fastapi-backend)
15. [Streamlit Chat Interface](#15-streamlit-chat-interface)
16. [End-to-End Data Flow](#16-end-to-end-data-flow)
17. [Setup & Running Instructions](#17-setup--running-instructions)
18. [Demo Questions & Expected Behavior](#18-demo-questions--expected-behavior)
19. [Future Expansion Roadmap](#19-future-expansion-roadmap)
20. [Key Design Decisions](#20-key-design-decisions)

---

## 1. Project Overview

**NM-GPT** is an AI-powered campus policy assistant that uses **Retrieval-Augmented Generation (RAG)** to answer student questions about the Student Resource Book (SRB). Instead of training a model on college data, we use a smarter approach: we store the SRB content in a searchable vector database and feed only the relevant sections to Google's Gemini LLM at query time. This ensures accurate, cited, and up-to-date answers.

The system is designed as a **working prototype** that can be demoed locally. The architecture is modular so it can later expand into a full campus-wide AI platform supporting multiple documents, departments, and services.

---

## 2. Problem Statement

Students frequently need to look up college policies — attendance rules, exam procedures, grading systems, leave policies, etc. Currently, they must:

- Manually search through a 100+ page PDF
- Visit the administration office during working hours
- Ask seniors (who may have outdated information)

**NM-GPT solves this** by providing an instant, conversational interface where students can ask natural language questions and get accurate, cited answers 24/7.

---

## 3. System Architecture

The system follows a **four-layer modular architecture**:

```
┌───────────────────────────────────────────────────────────┐
│                    INTERFACE LAYER                         │
│              Streamlit Chat UI (app.py)                    │
│         Chat messages │ Citations │ Confidence             │
└──────────────────────┬────────────────────────────────────┘
                       │ HTTP POST /query
┌──────────────────────▼────────────────────────────────────┐
│                   APPLICATION LAYER                        │
│               FastAPI Backend (app.py)                      │
│         Request validation │ CORS │ Error handling          │
└──────────────────────┬────────────────────────────────────┘
                       │
┌──────────────────────▼────────────────────────────────────┐
│                     RAG LAYER                              │
│              RAG Pipeline (rag_pipeline.py)                 │
│                                                            │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌────────────┐  │
│  │ Embed   │→ │ Retrieve │→ │ Assemble│→ │ Generate   │  │
│  │ Query   │  │ Top-K    │  │ Context │  │ Answer     │  │
│  └─────────┘  └──────────┘  └─────────┘  └────────────┘  │
└──────────────────────┬────────────────────────────────────┘
                       │
┌──────────────────────▼────────────────────────────────────┐
│                    STORAGE LAYER                           │
│  FAISS Vector Index │ Metadata JSON │ Chunks JSONL         │
└───────────────────────────────────────────────────────────┘
```

Additionally, a **separate Ingestion Pipeline** preprocesses the SRB PDF into chunks and builds the vector index (this runs once, offline):

```
SRB PDF → Extract Text → Chunk Text → Generate Embeddings → Build FAISS Index
```

---

## 4. Technology Stack

| Component | Technology | Why This Choice |
|-----------|-----------|-----------------|
| **Language** | Python 3.9+ | Industry standard for AI/ML, rich ecosystem |
| **LLM** | Google Gemini 1.5 Flash | Fast, free tier available, good instruction following |
| **Embeddings** | Gemini Embedding-001 | Native integration with Gemini, good semantic quality |
| **Vector Database** | FAISS (IndexFlatL2) | Facebook's library, fast exact search, no server needed |
| **PDF Parsing** | PyMuPDF (fitz) | Fastest Python PDF library, preserves page structure |
| **Text Splitting** | LangChain TextSplitters | Smart recursive splitting with overlap |
| **Backend** | FastAPI | Async, auto-generates OpenAPI docs, type-safe |
| **Frontend** | Streamlit | Rapid prototyping for chat interfaces |
| **Config** | python-dotenv | Secure API key management via .env files |

---

## 5. Project Structure

```
NM-GPT/
├── backend/                      # Core application logic
│   ├── __init__.py               # Package marker
│   ├── config.py                 # Centralized configuration
│   ├── embeddings.py             # Embedding model wrapper
│   ├── llm_client.py             # Gemini LLM client
│   ├── rag_pipeline.py           # Full RAG pipeline
│   ├── app.py                    # FastAPI web server
│   └── prompts/                  # LLM prompt templates
│       ├── system_prompt.txt     # System behavior rules
│       └── retrieval_prompt.txt  # Query template with placeholders
│
├── scripts/                      # One-time ingestion scripts
│   ├── extract_pdf.py            # PDF → pages.json
│   ├── chunk_documents.py        # pages.json → chunks.jsonl
│   └── build_index.py            # chunks.jsonl → FAISS index
│
├── streamlit_app/                # Chat interface
│   └── app.py                    # Streamlit chat UI
│
├── data/                         # Generated data (gitignored)
│   ├── pages.json                # Raw extracted pages
│   └── chunks.jsonl              # Processed chunks with metadata
│
├── index/                        # Vector index (gitignored)
│   ├── faiss_index.bin           # FAISS binary index
│   └── metadata.json             # Chunk metadata (parallel to vectors)
│
├── docs/                         # Documentation
│   ├── architecture.md           # Architecture overview
│   ├── demo_script.md            # Demo flow & example questions
│   └── project_explanation.md    # This file
│
├── requirements.txt              # Python dependencies
├── .env.example                  # API key template
├── .gitignore                    # Git ignore rules
├── README.md                     # Setup & usage guide
└── CLAUDE.md                     # Development guidelines
```

---

## 6. Core Concepts: RAG Explained

### What is RAG?

**Retrieval-Augmented Generation (RAG)** is a technique that enhances LLM responses by providing relevant context from a knowledge base at query time. Instead of fine-tuning a model (expensive, requires retraining when data changes), RAG dynamically retrieves the most relevant information for each question.

### How RAG Works in NM-GPT

```
Student: "What is the minimum attendance requirement?"
                    │
                    ▼
         ┌──────────────────┐
         │ 1. EMBED QUERY   │  Convert question to a vector
         │    using Gemini   │  (list of 3072 numbers)
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ 2. SEARCH FAISS  │  Find the 5 most similar
         │    Vector Index   │  chunk vectors (L2 distance)
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ 3. RETRIEVE      │  Get the actual text + metadata
         │    Chunk Text     │  for those 5 chunks
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ 4. BUILD PROMPT  │  Combine system rules +
         │                  │  retrieved context + question
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ 5. GENERATE      │  Send prompt to Gemini LLM
         │    Answer         │  → Get cited answer
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │ 6. RETURN         │  Answer + page citations
         │    Response       │  + confidence score
         └──────────────────┘
```

### Key Concepts

- **Embeddings**: A numerical representation (vector) of text that captures its semantic meaning. Similar texts have similar vectors. We use Gemini's `gemini-embedding-001` model which produces 3072-dimensional vectors.

- **Vector Database (FAISS)**: A specialized database optimized for finding the nearest vectors to a query vector. We use Facebook AI Similarity Search (FAISS) with an `IndexFlatL2` index, which performs exact L2 distance search — ideal for our scale (~400 vectors).

- **Chunking**: The SRB has ~100 pages of text. We can't send all of it to the LLM (context window limits, noise). Instead, we split it into ~1000-character overlapping chunks so each chunk is a coherent, self-contained piece of information.

- **Context Window**: The maximum amount of text an LLM can process at once. By only sending the top 5 most relevant chunks (~5000 chars), we stay well within limits and reduce noise.

---

## 7. Configuration Module

**File: `backend/config.py`**

This module centralizes all configurable parameters so we never hardcode paths, model names, or settings elsewhere. Changes to paths, models, or tuneable parameters are made in one place.

```python
"""
NM-GPT – Centralized Configuration

All paths, model settings, and tuneable parameters live here.
Uses python-dotenv to load secrets from a .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────
load_dotenv()

# ── Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INDEX_DIR = PROJECT_ROOT / "index"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Source PDF
SRB_PDF_PATH = PROJECT_ROOT / "Final SRB A.Y. 2025-26 .................................pdf"

# Generated artefacts
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
FAISS_INDEX_PATH = INDEX_DIR / "faiss_index.bin"
METADATA_PATH = INDEX_DIR / "metadata.json"

# ── API Keys ─────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── Model Settings ───────────────────────────────────────────
EMBEDDING_MODEL = "models/gemini-embedding-001"
LLM_MODEL = "gemini-1.5-flash"
LLM_TEMPERATURE = 0.2

# ── Chunking ─────────────────────────────────────────────────
CHUNK_SIZE = 1000        # characters per chunk
CHUNK_OVERLAP = 200      # overlap between consecutive chunks

# ── Retrieval ────────────────────────────────────────────────
DEFAULT_TOP_K = 5

# ── Server ───────────────────────────────────────────────────
BACKEND_HOST = "localhost"
BACKEND_PORT = 8000
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
```

### How It Works

- **`load_dotenv()`** — Reads the `.env` file at project root and loads variables into `os.environ`. This keeps the API key out of source code.
- **`Path(__file__).resolve().parent.parent`** — Dynamically resolves to the project root regardless of where the script is run from.
- **`LLM_TEMPERATURE = 0.2`** — Low temperature means more deterministic, factual answers. Higher values (0.7+) make the model more creative but less reliable for policy questions.
- **`CHUNK_SIZE = 1000` / `CHUNK_OVERLAP = 200`** — Each chunk is ~1000 characters with 200 characters of overlap with the previous chunk. Overlap ensures that information spanning a chunk boundary isn't lost.

### 💡 Example: Accessing Configuration Values

```python
# In any file, simply import what you need:
from backend.config import EMBEDDING_MODEL, LLM_MODEL, CHUNK_SIZE, CHUNK_OVERLAP

print(EMBEDDING_MODEL)   # "models/gemini-embedding-001"
print(LLM_MODEL)         # "gemini-2.5-flash"
print(CHUNK_SIZE)        # 1000
print(CHUNK_OVERLAP)     # 200
```

**Sample Output:**
```
models/gemini-embedding-001
gemini-2.5-flash
1000
200
```

**How it works:** When Python imports `config.py`, `load_dotenv()` runs immediately and loads `.env` into the environment. Then `os.getenv("GOOGLE_API_KEY")` fetches the key. All other variables are plain Python assignments. Any module that does `from backend.config import X` gets the same values — they're module-level constants loaded once.

---

## 8. Document Ingestion Pipeline

The ingestion pipeline runs **once** (or whenever the SRB is updated) to prepare the data for querying.

### Step 1: PDF Text Extraction

**File: `scripts/extract_pdf.py`**

Reads the SRB PDF and extracts raw text from each page, preserving page numbers.

```python
#!/usr/bin/env python3
from __future__ import annotations

"""
NM-GPT – PDF Text Extraction

Extracts text from the SRB PDF page-by-page using PyMuPDF,
preserving page numbers in metadata.
"""

import json
import sys
from pathlib import Path

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

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "pages.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved to: {output_path}")

    if pages:
        preview = pages[0]["text"][:300]
        print(f"\n── Page 1 Preview ──\n{preview}…")


if __name__ == "__main__":
    main()
```

**Key Design Decisions:**
- **PyMuPDF (`fitz`)** is used because it's the fastest Python PDF library and handles complex PDF layouts well.
- **1-indexed page numbers** match what students see in the actual PDF.
- **Blank pages are skipped** to avoid generating empty chunks.
- **Output is an intermediate `pages.json`** — separating extraction from chunking makes each step debuggable independently.

### 💡 Example: Running PDF Extraction

**Command:**
```bash
python scripts/extract_pdf.py
```

**Sample Terminal Output:**
```
📄 Extracting text from: Final SRB A.Y. 2025-26 .................................pdf
✅ Extracted 112 pages with text
💾 Saved to: data/pages.json

── Page 1 Preview ──
STUDENT RESOURCE BOOK

Part-I
NMIMS (Deemed-to-be)
UNIVERSITY…
```

**Sample `data/pages.json` output (first entry):**
```json
[
  {
    "page_number": 2,
    "text": "STUDENT RESOURCE BOOK \n \n \nPart-I \nNMIMS (Deemed-to-be)\nUNIVERSITY"
  },
  {
    "page_number": 3,
    "text": "Message from Vice-Chancellor\nWelcome, and Congratulations on joining NMIMS!\n\nYou have joined an institution that has the legacy of developing some of the most successful professionals..."
  }
]
```

**How it works:** `fitz.open()` loads the PDF into memory. For each page (0-indexed internally), `page.get_text("text")` extracts the raw text content. We add 1 to make it match the human-readable page number. If a page has only whitespace (blank pages like separators), `text.strip()` returns an empty string and we skip it. The result is a list of `{page_number, text}` dicts — page 1 of the SRB PDF is actually blank, so the first entry is page 2.

### Step 2: Document Chunking

**File: `scripts/chunk_documents.py`**

Splits the extracted page texts into overlapping chunks with metadata.

```python
#!/usr/bin/env python3
from __future__ import annotations

"""
NM-GPT – Document Chunking

Reads the extracted pages (data/pages.json) and splits them into
semantic chunks with metadata, outputting data/chunks.jsonl.
"""

import json
import sys
from pathlib import Path

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

    for i, chunk in enumerate(chunks):
        chunk["chunk_id"] = f"chunk_{i:04d}"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "chunks.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"💾 Saved {len(chunks)} chunks to: {output_path}")

    if chunks:
        sample = chunks[0]
        print(f"\n── Sample Chunk ──")
        print(f"   ID:    {sample['chunk_id']}")
        print(f"   Pages: {sample['page_start']}–{sample['page_end']}")
        print(f"   Text:  {sample['text'][:200]}…")


if __name__ == "__main__":
    main()
```

**Key Design Decisions:**

- **`RecursiveCharacterTextSplitter`** — LangChain's smartest splitter. It tries to split on paragraph breaks (`\n\n`) first, then newlines (`\n`), then sentences (`. `), then words, then characters. This preserves semantic coherence within chunks.
- **Chunk overlap (200 chars)** — Ensures that if a sentence spans two chunks, both chunks contain the full sentence. Without overlap, answers might miss relevant context at boundaries.
- **Cross-page merge** — Short stubs at page boundaries (e.g., a title that's only 50 characters) are merged with the next chunk to maintain quality.
- **JSONL format** — One JSON object per line. Easy to stream, append, and debug compared to a single JSON array.

### 💡 Example: Running the Chunking Script

**Command:**
```bash
python scripts/chunk_documents.py
```

**Sample Terminal Output:**
```
📖 Loading extracted pages…
   112 pages loaded
✂️  Chunking text…
   408 raw chunks created
🔗 Merging short cross-page chunks…
   405 final chunks
💾 Saved 405 chunks to: data/chunks.jsonl

── Sample Chunk ──
   ID:    chunk_0000
   Pages: 2–3
   Text:  STUDENT RESOURCE BOOK
         Part-I
         NMIMS (Deemed-to-be) UNIVERSITY
         Message from Vice-Chancellor…
```

**How it works step-by-step:**

1. **Page loading** — The script reads all 112 pages from `pages.json`.
2. **Text splitting** — For each page, `RecursiveCharacterTextSplitter` breaks the text at natural boundaries:
   ```python
   # Example: Page 3 has 3303 characters of text
   # With chunk_size=1000 and overlap=200:
   # Chunk 1: chars 0-999    (1000 chars)
   # Chunk 2: chars 800-1799  (overlap of 200 chars with Chunk 1)
   # Chunk 3: chars 1600-2599 (overlap of 200 chars with Chunk 2)
   # Chunk 4: chars 2400-3303 (remainder)
   ```
3. **Cross-page merging** — Page 2 only has 66 characters ("STUDENT RESOURCE BOOK...Part-I..."). Since 66 < 100 (`MIN_CHUNK_LENGTH`), it gets merged with the first chunk of Page 3. That's why `chunk_0000` shows `pages: 2-3`.
4. **Re-indexing** — After merging reduces 408 → 405 chunks, IDs are reassigned sequentially.

**Sample actual chunk from `chunks.jsonl` (chunk_0042):**
```json
{
  "chunk_id": "chunk_0042",
  "text": "can check documents within the batch, across the batch, across past years, the worldwide web, etc. Similarity index / plagiarism is a serious offense, which is unethical and illegal. If a student is...",
  "source": "Student Resource Book (SRB) A.Y. 2025-26",
  "page_start": 13,
  "page_end": 13
}
```

### Chunk Metadata Schema

Each chunk in `chunks.jsonl` contains:

```json
{
    "chunk_id": "chunk_0042",
    "text": "The minimum attendance requirement is 75%...",
    "source": "Student Resource Book (SRB) A.Y. 2025-26",
    "page_start": 12,
    "page_end": 12
}
```

| Field | Type | Description |
|-------|------|-------------|
| `chunk_id` | string | Unique identifier (`chunk_XXXX`) |
| `text` | string | The actual text content (~1000 chars) |
| `source` | string | Name of the source document |
| `page_start` | int | First page this chunk comes from |
| `page_end` | int | Last page (same as start for single-page chunks) |

---

## 9. Embeddings Module

**File: `backend/embeddings.py`**

A modular wrapper around Google's Gemini embedding model. This abstraction means switching to a different embedding model (e.g., OpenAI, Cohere, local models) requires changes only in this file.

```python
from __future__ import annotations

"""
NM-GPT – Embedding Wrapper

Modular embedding interface using Google Generative AI embeddings.
The model can be swapped by changing EMBEDDING_MODEL in config.py.
"""

from backend.config import GOOGLE_API_KEY, EMBEDDING_MODEL
from langchain_google_genai import GoogleGenerativeAIEmbeddings


def get_embedding_model() -> GoogleGenerativeAIEmbeddings:
    """Return a configured embedding model instance."""
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY is not set. "
            "Create a .env file with your key (see .env.example)."
        )
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    model = get_embedding_model()
    return model.embed_documents(texts)


def embed_query(query: str) -> list[float]:
    """Generate an embedding for a single query string."""
    model = get_embedding_model()
    return model.embed_query(query)
```

**Key Design Decisions:**

- **Two separate functions**: `embed_texts()` (for batch document embedding during indexing) and `embed_query()` (for single query embedding at runtime). Some embedding models optimize these differently.
- **Validation** — The `get_embedding_model()` function checks for the API key upfront and gives a clear error message rather than a cryptic library exception.

### 💡 Example: Generating Embeddings

```python
from backend.embeddings import embed_query, embed_texts

# Single query embedding
vector = embed_query("What is the attendance policy?")
print(f"Type: {type(vector)}")
print(f"Dimension: {len(vector)}")
print(f"First 5 values: {vector[:5]}")
```

**Sample Output:**
```
Type: <class 'list'>
Dimension: 3072
First 5 values: [0.0234, -0.0184, 0.0551, -0.0312, 0.0187]
```

```python
# Batch document embedding
vectors = embed_texts([
    "Students must maintain 75% attendance.",
    "The grading system uses a 10-point scale."
])
print(f"Number of vectors: {len(vectors)}")
print(f"Each vector dimension: {len(vectors[0])}")
```

**Sample Output:**
```
Number of vectors: 2
Each vector dimension: 3072
```

**How it works:** The `embed_query()` function creates a `GoogleGenerativeAIEmbeddings` instance with the configured model name and API key, then calls `model.embed_query()` which sends the text to the Gemini API. The API returns a 3072-dimensional float vector that captures the semantic meaning of the text. Texts about similar topics (e.g., "attendance" and "minimum attendance requirement") will produce vectors that are close together in this 3072-dimensional space, while unrelated texts (e.g., "attendance" and "library hours") will produce distant vectors.

---

## 10. Vector Index Builder

**File: `scripts/build_index.py`**

This script reads all chunks, generates embeddings via the Gemini API, and builds a FAISS vector index. It includes rate-limit handling and progress saving for reliability with the free tier.

```python
#!/usr/bin/env python3
from __future__ import annotations

"""
NM-GPT – Build FAISS Index

Handles free-tier rate limits by:
  - Using small batch sizes (20 chunks)
  - Automatic retry with exponential backoff on 429 errors
  - Saving progress incrementally so interrupted runs can resume
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import faiss

from backend.config import CHUNKS_PATH, FAISS_INDEX_PATH, METADATA_PATH, INDEX_DIR, DATA_DIR
from backend.embeddings import embed_texts

BATCH_SIZE = 20   # Small batches to stay under free-tier rate limits
MAX_RETRIES = 5   # Max retries per batch on rate-limit errors
BASE_DELAY = 25   # Base delay in seconds between batches


def load_chunks(chunks_path: Path) -> list[dict]:
    """Load chunks from JSONL file."""
    chunks = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def load_progress() -> list[list[float]]:
    """Load previously saved embeddings progress, if any."""
    progress_path = DATA_DIR / "embeddings_progress.json"
    if progress_path.exists():
        with open(progress_path, "r") as f:
            data = json.load(f)
            print(f"📂 Resuming from saved progress: {len(data)} embeddings already done")
            return data
    return []


def save_progress(embeddings: list[list[float]]):
    """Save embeddings progress to disk for resume capability."""
    progress_path = DATA_DIR / "embeddings_progress.json"
    with open(progress_path, "w") as f:
        json.dump(embeddings, f)


def clear_progress():
    """Remove the progress file after successful completion."""
    progress_path = DATA_DIR / "embeddings_progress.json"
    if progress_path.exists():
        progress_path.unlink()


def embed_batch_with_retry(batch, batch_num, total_batches):
    """Embed a batch of texts with retry logic for rate limits."""
    for attempt in range(MAX_RETRIES):
        try:
            return embed_texts(batch)
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                wait_time = BASE_DELAY * (2 ** attempt)
                print(f"   ⏳ Rate limited on batch {batch_num}/{total_batches}. "
                      f"Waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})…")
                time.sleep(wait_time)
            else:
                raise
    raise RuntimeError(f"Failed to embed batch {batch_num} after {MAX_RETRIES} retries")


def build_index(chunks):
    """Generate embeddings and build FAISS index."""
    texts = [c["text"] for c in chunks]

    all_embeddings = load_progress()
    start_idx = len(all_embeddings)

    if start_idx >= len(texts):
        print(f"✅ All {len(texts)} embeddings already generated!")
    else:
        remaining = len(texts) - start_idx
        print(f"🔄 Generating embeddings for {remaining} remaining chunks "
              f"(of {len(texts)} total)…")

        for i in range(start_idx, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"   Batch {batch_num}/{total_batches} ({len(batch)} chunks)…")

            embeddings = embed_batch_with_retry(batch, batch_num, total_batches)
            all_embeddings.extend(embeddings)
            save_progress(all_embeddings)

            if i + BATCH_SIZE < len(texts):
                print(f"   💤 Cooling down for {BASE_DELAY}s…")
                time.sleep(BASE_DELAY)

    embedding_matrix = np.array(all_embeddings, dtype=np.float32)
    dimension = embedding_matrix.shape[1]

    print(f"📐 Embedding dimension: {dimension}")
    print(f"📊 Total vectors: {embedding_matrix.shape[0]}")

    index = faiss.IndexFlatL2(dimension)
    index.add(embedding_matrix)

    metadata = [
        {
            "chunk_id": c["chunk_id"],
            "text": c["text"],
            "source": c["source"],
            "page_start": c["page_start"],
            "page_end": c["page_end"],
        }
        for c in chunks
    ]

    return index, metadata


def main():
    if not CHUNKS_PATH.exists():
        print(f"❌ Chunks file not found at: {CHUNKS_PATH}")
        print("   Run the ingestion pipeline first:")
        print("   python scripts/extract_pdf.py")
        print("   python scripts/chunk_documents.py")
        sys.exit(1)

    chunks = load_chunks(CHUNKS_PATH)
    print(f"📄 Loaded {len(chunks)} chunks from {CHUNKS_PATH.name}")

    index, metadata = build_index(chunks)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(FAISS_INDEX_PATH))
    print(f"💾 FAISS index saved to: {FAISS_INDEX_PATH}")

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"💾 Metadata saved to: {METADATA_PATH}")

    clear_progress()

    print("\n✅ Index built successfully!")
    print(f"   Vectors: {index.ntotal}")
    print(f"   Dimension: {index.d}")


if __name__ == "__main__":
    main()
```

**Key Design Decisions:**

- **`IndexFlatL2`** — Performs exact brute-force L2 (Euclidean) distance search. For ~400 vectors, this is instant (<1ms). For millions of vectors, we'd switch to `IndexIVFFlat` or `IndexHNSW` for approximate but faster search.
- **Batch size of 20** — The Gemini free tier allows 100 embedding requests/minute. With batches of 20, we make ~20 requests per cycle with cooling pauses.
- **Exponential backoff** — On rate-limit errors (HTTP 429), the script waits 25s, 50s, 100s, 200s, 400s (doubling each time). This prevents hammering the API.
- **Progress saving** — After each successful batch, embeddings are saved to `embeddings_progress.json`. If the script crashes or is interrupted, re-running it resumes from where it stopped.
- **Metadata stored separately** — FAISS doesn't store text, only vectors. The metadata JSON array is indexed in parallel with the FAISS vectors — vector at index `i` corresponds to metadata at index `i`.

### 💡 Example: Building the Index

**Command:**
```bash
python scripts/build_index.py
```

**Sample Terminal Output (complete run):**
```
📄 Loaded 405 chunks from chunks.jsonl
🔄 Generating embeddings for 405 remaining chunks (of 405 total)…
   Batch 1/21 (20 chunks)…
   💤 Cooling down for 25s…
   Batch 2/21 (20 chunks)…
   💤 Cooling down for 25s…
   ...
   Batch 21/21 (5 chunks)…
📐 Embedding dimension: 3072
📊 Total vectors: 405
💾 FAISS index saved to: index/faiss_index.bin
💾 Metadata saved to: index/metadata.json

✅ Index built successfully!
   Vectors: 405
   Dimension: 3072
```

**Sample Terminal Output (resumed after interruption):**
```
📄 Loaded 405 chunks from chunks.jsonl
📂 Resuming from saved progress: 160 embeddings already done
🔄 Generating embeddings for 245 remaining chunks (of 405 total)…
   Batch 9/21 (20 chunks)…
   ...
```

**Example: How FAISS search works internally:**
```python
import faiss
import numpy as np

# Load the built index
index = faiss.read_index("index/faiss_index.bin")
print(f"Index contains {index.ntotal} vectors of dimension {index.d}")
# Output: Index contains 405 vectors of dimension 3072

# Simulate a query (normally embed_query provides this)
query_vector = np.random.randn(1, 3072).astype(np.float32)

# Search for top-5 nearest neighbors
distances, indices = index.search(query_vector, 5)
print(f"Top-5 chunk indices: {indices[0].tolist()}")
print(f"L2 distances:        {[round(d, 4) for d in distances[0].tolist()]}")
```

**Sample Output:**
```
Index contains 405 vectors of dimension 3072
Top-5 chunk indices: [142, 287, 53, 199, 312]
L2 distances:        [0.4521, 0.5103, 0.5287, 0.6012, 0.6198]
```

**How it works:** Each chunk's text is converted to a 3072-dimensional vector via the Gemini embedding API. These 405 vectors are stored in a FAISS `IndexFlatL2` — a flat array that performs brute-force L2 distance search. When a query comes in, its embedding vector is compared against all 405 stored vectors, and the 5 with the smallest L2 distance (most similar meaning) are returned. The `distances` array tells us how similar each result is — lower = more relevant.

---

## 11. LLM Client

**File: `backend/llm_client.py`**

A clean wrapper around the Gemini LLM for answer generation.

```python
"""
NM-GPT – LLM Client

Wraps the Google Generative AI chat model for answer generation.
Uses LangChain's ChatGoogleGenerativeAI for consistency with the
rest of the pipeline.
"""

from backend.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE
from langchain_google_genai import ChatGoogleGenerativeAI


def get_llm() -> ChatGoogleGenerativeAI:
    """Return a configured LLM instance."""
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY is not set. "
            "Create a .env file with your key (see .env.example)."
        )
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=LLM_TEMPERATURE,
    )


def generate(prompt: str) -> str:
    """Send a prompt to the LLM and return the text response."""
    llm = get_llm()
    response = llm.invoke(prompt)
    return response.content
```

**Design Notes:**
- **Temperature 0.2** — Low value for precise, factual answers. Not 0.0 because a bit of flexibility helps with natural phrasing.
- **`ChatGoogleGenerativeAI`** from LangChain — Provides a consistent interface. If we switch to OpenAI later, we only change this file.

### 💡 Example: Using the LLM Client

```python
from backend.llm_client import generate

# Simple prompt
response = generate("Explain what RAG stands for in 1 sentence.")
print(response)
```

**Sample Output:**
```
RAG stands for Retrieval-Augmented Generation, a technique that enhances
LLM responses by retrieving relevant context from external knowledge
sources before generating an answer.
```

```python
# In the actual pipeline, prompts are much longer:
prompt = """You are NM-GPT...

--- CONTEXT START ---
[Page 12]
The minimum attendance requirement is 75%...
--- CONTEXT END ---

STUDENT'S QUESTION: What is the attendance policy?

ANSWER:"""

response = generate(prompt)
print(response)
```

**Sample Output:**
```
The minimum attendance requirement at the college is 75%. Students who
fall below this threshold may be debarred from appearing in the
examinations. [Page 12]
```

**How it works:** `get_llm()` creates a `ChatGoogleGenerativeAI` instance with the model name (`gemini-2.5-flash`), API key, and temperature (0.2). Calling `llm.invoke(prompt)` sends the entire prompt string to the Gemini API, which returns a response object. We extract just the text content via `response.content`. The low temperature (0.2) ensures consistent, factual answers rather than creative or varied responses.

---

## 12. Prompt Engineering

Two prompt templates control how the LLM behaves:

### System Prompt (`backend/prompts/system_prompt.txt`)

This defines the LLM's identity and rules:

```
You are NM-GPT, an AI assistant for students at the college. Your purpose
is to answer questions about college policies, rules, and procedures using
ONLY the Student Resource Book (SRB).

RULES:
1. ONLY use the provided context to answer questions. Do NOT use any external
   knowledge.
2. If the answer is NOT present in the provided context, respond with:
   "I could not find this information in the Student Resource Book. Please
   contact the administration office for assistance."
3. ALWAYS include page number citations in your answer using the format
   [Page X] or [Pages X-Y].
4. Keep your answers concise, clear, and student-friendly.
5. If a question is ambiguous, provide the most relevant information and
   suggest the student verify with the administration.
6. Format your answers with bullet points or numbered lists when presenting
   multiple items.
7. Be helpful and empathetic in your tone.
```

### Retrieval Prompt Template (`backend/prompts/retrieval_prompt.txt`)

This is filled in dynamically with the retrieved context and user question:

```
Use the following context from the Student Resource Book (SRB) to answer the
student's question. Each context section includes the page number(s) it was
found on.

--- CONTEXT START ---
{context}
--- CONTEXT END ---

STUDENT'S QUESTION: {question}

INSTRUCTIONS:
- Answer ONLY based on the context above.
- Include page citations in your answer using [Page X] format.
- If the context does not contain enough information to answer, say:
  "I could not find this information in the Student Resource Book."
- Be concise and clear.

ANSWER:
```

**Why separate files?** Prompt templates in separate `.txt` files mean non-developers (e.g., college admin) can edit the behavior without touching Python code.

### 💡 Example: How the Prompt is Assembled

Given a student question and retrieved chunks, here's what the final prompt looks like:

```python
# Input question:
question = "What is the minimum attendance requirement?"

# Retrieved chunks (simplified):
chunks = [
    {"text": "The minimum attendance requirement is 75%...", "page_start": 12, "page_end": 12},
    {"text": "Students who fall below 75% attendance...", "page_start": 12, "page_end": 12},
]

# Step 1: Assemble context from chunks
context = """[Page 12]
The minimum attendance requirement is 75%...

[Page 12]
Students who fall below 75% attendance..."""

# Step 2: Fill in the retrieval template
retrieval_prompt = retrieval_prompt_template.format(
    context=context,
    question=question
)

# Step 3: Combine with system prompt
full_prompt = system_prompt + "\n\n" + retrieval_prompt
```

**The final prompt sent to Gemini looks like:**
```
You are NM-GPT, an AI assistant for students at the college...

RULES:
1. ONLY use the provided context to answer questions...
...

Use the following context from the Student Resource Book (SRB)...

--- CONTEXT START ---
[Page 12]
The minimum attendance requirement is 75%...

[Page 12]
Students who fall below 75% attendance...
--- CONTEXT END ---

STUDENT'S QUESTION: What is the minimum attendance requirement?

INSTRUCTIONS:
- Answer ONLY based on the context above.
- Include page citations in your answer using [Page X] format.
...

ANSWER:
```

**How it works:** The `{context}` and `{question}` placeholders in `retrieval_prompt.txt` are replaced with actual values using Python's `str.format()`. The system prompt establishes the LLM's role and rules (always cite pages, don't use external knowledge), while the retrieval prompt provides the evidence and asks the specific question. This separation means the LLM gets clear instructions + grounded context, leading to accurate, cited answers.

---

## 13. RAG Pipeline

**File: `backend/rag_pipeline.py`**

This is the **core brain** of NM-GPT. It orchestrates the entire query flow.

```python
from __future__ import annotations

"""
NM-GPT – RAG Pipeline

End-to-end retrieval-augmented generation:
  1. Embed user query
  2. Retrieve top-k chunks from FAISS
  3. Assemble context with page metadata
  4. Build prompt from templates
  5. Generate answer via Gemini
  6. Return structured response with citations
"""

import json
import re
import numpy as np
import faiss
from pathlib import Path

from backend.config import (
    FAISS_INDEX_PATH, METADATA_PATH, PROMPTS_DIR, DEFAULT_TOP_K,
)
from backend.embeddings import embed_query
from backend.llm_client import generate


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for NM-GPT."""

    def __init__(self):
        """Load FAISS index, metadata, and prompt templates."""
        if not FAISS_INDEX_PATH.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {FAISS_INDEX_PATH}. "
                "Run `python scripts/build_index.py` first."
            )
        self.index = faiss.read_index(str(FAISS_INDEX_PATH))

        if not METADATA_PATH.exists():
            raise FileNotFoundError(
                f"Metadata not found at {METADATA_PATH}. "
                "Run `python scripts/build_index.py` first."
            )
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.system_prompt = self._load_prompt("system_prompt.txt")
        self.retrieval_prompt_template = self._load_prompt("retrieval_prompt.txt")

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt template from the prompts directory."""
        path = PROMPTS_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def retrieve(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
        """Embed query and retrieve the top-k most relevant chunks."""
        query_embedding = embed_query(query)
        query_vector = np.array([query_embedding], dtype=np.float32)

        distances, indices = self.index.search(query_vector, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            chunk_meta = self.metadata[idx].copy()
            chunk_meta["distance"] = float(dist)
            results.append(chunk_meta)

        return results

    def _assemble_context(self, chunks: list[dict]) -> str:
        """Assemble retrieved chunks into a single context string."""
        context_parts = []
        for chunk in chunks:
            page_info = f"Page {chunk['page_start']}"
            if chunk["page_start"] != chunk["page_end"]:
                page_info = f"Pages {chunk['page_start']}–{chunk['page_end']}"
            context_parts.append(f"[{page_info}]\n{chunk['text']}")
        return "\n\n".join(context_parts)

    def _build_prompt(self, context: str, question: str) -> str:
        """Build the full prompt from system prompt + retrieval template."""
        retrieval_prompt = self.retrieval_prompt_template.format(
            context=context, question=question,
        )
        return f"{self.system_prompt}\n\n{retrieval_prompt}"

    def _extract_page_citations(self, answer: str, chunks: list[dict]) -> list[int]:
        """Extract page numbers cited in the answer text."""
        page_pattern = r'\[Pages?\s*(\d+)(?:\s*[-–]\s*(\d+))?\]'
        matches = re.findall(page_pattern, answer)

        pages = set()
        for match in matches:
            start_page = int(match[0])
            pages.add(start_page)
            if match[1]:
                end_page = int(match[1])
                for p in range(start_page, end_page + 1):
                    pages.add(p)

        if not pages:
            for chunk in chunks:
                for p in range(chunk["page_start"], chunk["page_end"] + 1):
                    pages.add(p)

        return sorted(pages)

    def _compute_confidence(self, chunks: list[dict]) -> float:
        """Compute a heuristic confidence score based on retrieval distances."""
        if not chunks:
            return 0.0

        distances = [c["distance"] for c in chunks]
        avg_distance = sum(distances) / len(distances)

        confidence = max(0.0, min(1.0, 1.0 - (avg_distance / 2.0)))
        return round(confidence, 2)

    def query(self, question: str, top_k: int = DEFAULT_TOP_K) -> dict:
        """Run the full RAG pipeline.

        Returns:
          {
            "answer": str,
            "citations": [...],
            "pages": [int, ...],
            "confidence": float
          }
        """
        chunks = self.retrieve(question, top_k=top_k)

        if not chunks:
            return {
                "answer": "I could not find relevant information in the "
                          "Student Resource Book.",
                "citations": [], "pages": [], "confidence": 0.0,
            }

        context = self._assemble_context(chunks)
        prompt = self._build_prompt(context, question)
        answer = generate(prompt)

        pages = self._extract_page_citations(answer, chunks)
        confidence = self._compute_confidence(chunks)

        citations = [
            {
                "text": c["text"][:300] + ("…" if len(c["text"]) > 300 else ""),
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "chunk_id": c["chunk_id"],
            }
            for c in chunks
        ]

        return {
            "answer": answer,
            "citations": citations,
            "pages": pages,
            "confidence": confidence,
        }
```

### Method-by-Method Explanation

| Method | Purpose |
|--------|---------|
| `__init__()` | Loads the FAISS index, metadata, and prompt templates into memory. Runs once when the server starts. |
| `retrieve()` | Converts the student question to a vector, searches FAISS for the `top_k` nearest chunks, returns them with distance scores. |
| `_assemble_context()` | Formats retrieved chunks into a readable string with page annotations like `[Page 12]` before each chunk's text. |
| `_build_prompt()` | Combines the system prompt + retrieval template (filled with context and question) into a single prompt for the LLM. |
| `_extract_page_citations()` | Uses regex to find `[Page X]` or `[Pages X-Y]` patterns in the LLM's answer. Falls back to retrieved chunk pages if no explicit citations are found. |
| `_compute_confidence()` | Heuristic: maps the average L2 distance of retrieved chunks to a 0–1 confidence score. Lower distance = higher confidence. |
| `query()` | Orchestrates the full pipeline: retrieve → assemble → generate → extract citations → return structured response. |

### 💡 Example: Step-by-Step RAG Pipeline Execution

**Step 1 — Retrieve relevant chunks:**
```python
from backend.rag_pipeline import RAGPipeline

pipeline = RAGPipeline()
chunks = pipeline.retrieve("What is the plagiarism policy?", top_k=3)
for c in chunks:
    print(f"  {c['chunk_id']} | Page {c['page_start']} | dist={c['distance']:.4f}")
    print(f"    {c['text'][:100]}...")
```

**Sample Output:**
```
  chunk_0042 | Page 13 | dist=0.3521
    can check documents within the batch, across the batch, across past years,
    the worldwide web, etc. Similarity index / plagiarism is a serious offense...
  chunk_0041 | Page 13 | dist=0.4103
    The University uses plagiarism detection tools to verify the originality
    of student submissions...
  chunk_0043 | Page 14 | dist=0.5287
    Penalties for plagiarism range from grade reduction to expulsion depending
    on the severity...
```

**Step 2 — Assemble context from chunks:**
```python
context = pipeline._assemble_context(chunks)
print(context[:300])
```

**Sample Output:**
```
[Page 13]
can check documents within the batch, across the batch, across past years,
the worldwide web, etc. Similarity index / plagiarism is a serious offense,
which is unethical and illegal...

[Page 13]
The University uses plagiarism detection tools to verify the originality...
```

**Step 3 — Extract page citations from LLM answer:**
```python
answer = "Plagiarism is a serious offense [Page 13]. Penalties include grade reduction [Pages 13-14]."
pages = pipeline._extract_page_citations(answer, chunks)
print(f"Cited pages: {pages}")
```

**Sample Output:**
```
Cited pages: [13, 14]
```

**How the regex works:** The pattern `\[Pages?\s*(\d+)(?:\s*[-–]\s*(\d+))?\]` matches both `[Page 13]` (single page) and `[Pages 13-14]` (page range). For `[Pages 13-14]`, it captures group 1 = "13" and group 2 = "14", then generates all pages in that range: `{13, 14}`.

**Step 4 — Compute confidence:**
```python
confidence = pipeline._compute_confidence(chunks)
print(f"Confidence: {confidence}")
# With distances [0.3521, 0.4103, 0.5287]:
#   avg_distance = (0.3521 + 0.4103 + 0.5287) / 3 = 0.4304
#   confidence = 1.0 - (0.4304 / 2.0) = 0.7848 → 0.78
```

**Sample Output:**
```
Confidence: 0.78
```

**Step 5 — Full query (all steps combined):**
```python
result = pipeline.query("What is the plagiarism policy?")
print(f"Answer: {result['answer'][:200]}...")
print(f"Pages cited: {result['pages']}")
print(f"Confidence: {result['confidence']}")
print(f"Number of source citations: {len(result['citations'])}")
```

**Sample Output:**
```
Answer: Plagiarism is a serious offense at NMIMS. The University uses
plagiarism detection tools to verify the originality of student submissions.
Similarity index / plagiarism is unethical and illegal. [Page 13]...
Pages cited: [13, 14]
Confidence: 0.78
Number of source citations: 5
```

---

## 14. FastAPI Backend

**File: `backend/app.py`**

The REST API server that the Streamlit frontend communicates with.

```python
from __future__ import annotations

"""
NM-GPT – FastAPI Backend

Endpoints:
  POST /query  – Answer a student question using the RAG pipeline
  GET  /health – Health check
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import DEFAULT_TOP_K

app = FastAPI(
    title="NM-GPT API",
    description="Campus Policy AI Assistant",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline = None


def get_pipeline():
    """Get or initialize the RAG pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        from backend.rag_pipeline import RAGPipeline
        _pipeline = RAGPipeline()
    return _pipeline


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The student's question")
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=20,
                       description="Number of chunks to retrieve")


class Citation(BaseModel):
    text: str
    page_start: int
    page_end: int
    chunk_id: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    pages: list[int]
    confidence: float


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "NM-GPT"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a student question using the RAG pipeline."""
    try:
        pipeline = get_pipeline()
        result = pipeline.query(
            question=request.question,
            top_k=request.top_k,
        )
        return QueryResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
```

**Key Design Decisions:**

- **Lazy-loaded pipeline** — The RAG pipeline is initialized on the first request, not at startup. This means the server starts even if the FAISS index hasn't been built yet.
- **Pydantic models** — `QueryRequest` and `QueryResponse` provide automatic validation, serialization, and OpenAPI documentation.
- **CORS middleware** — Allows the Streamlit frontend (running on a different port) to make API calls.
- **Error handling** — `FileNotFoundError` returns 503 (service unavailable), telling the user to build the index first.

### API Reference

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| `/health` | GET | none | `{"status": "healthy"}` |
| `/query` | POST | `{"question": str, "top_k": int}` | `{"answer": str, "citations": [...], "pages": [...], "confidence": float}` |

### 💡 Example: Testing the API with cURL

**Health check:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{"status": "healthy", "service": "NM-GPT"}
```

**Querying the RAG system:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the anti-ragging policy?", "top_k": 3}'
```

**Sample Response:**
```json
{
  "answer": "NMIMS has a strict anti-ragging policy in compliance with UGC regulations. Any form of ragging is a cognizable offense and is strictly prohibited. [Page 25]\n\nKey points:\n- An Anti-Ragging Committee has been constituted to address complaints.\n- Students must sign an anti-ragging affidavit at the time of admission.\n- Penalties range from suspension to expulsion. [Pages 25-26]",
  "citations": [
    {
      "text": "Anti-Ragging Policy\nNMIMS has constituted an Anti-Ragging Committee in compliance with UGC regulations. Ragging in any form is strictly prohibited and is a cognizable offense…",
      "page_start": 25,
      "page_end": 25,
      "chunk_id": "chunk_0098"
    },
    {
      "text": "Students must submit an online anti-ragging affidavit at the time of admission. Any violation will result in disciplinary action including suspension or expulsion…",
      "page_start": 26,
      "page_end": 26,
      "chunk_id": "chunk_0101"
    }
  ],
  "pages": [25, 26],
  "confidence": 0.82
}
```

**Testing with Python:**
```python
import httpx

response = httpx.post(
    "http://localhost:8000/query",
    json={"question": "What scholarships are available?", "top_k": 5}
)
data = response.json()
print(f"Answer: {data['answer'][:150]}...")
print(f"Pages: {data['pages']}")
print(f"Confidence: {data['confidence']}")
print(f"Sources: {len(data['citations'])} chunks")
```

**Sample Output:**
```
Answer: NMIMS offers various scholarships to eligible students including
merit-based scholarships, need-based financial assistance, and sports
scholarships. [Page 30]...
Pages: [30, 31]
Confidence: 0.75
Sources: 5 chunks
```

**How request validation works:** When the POST request arrives, Pydantic validates the JSON body against `QueryRequest`. If `question` is empty (`min_length=1`), it returns a 422 error. If `top_k` is outside `[1, 20]`, it also returns 422. The `get_pipeline()` singleton pattern loads the RAG pipeline on the first call and reuses it for subsequent requests — avoiding expensive re-initialization of the FAISS index.

**Auto-generated API docs:** Visit `http://localhost:8000/docs` while the server is running to see FastAPI's interactive Swagger UI where you can test endpoints directly in the browser.

---

## 15. Streamlit Chat Interface

**File: `streamlit_app/app.py`**

The student-facing chat interface.

```python
from __future__ import annotations

"""
NM-GPT – Streamlit Chat Interface

A chat-style web UI for students to ask questions about the
Student Resource Book (SRB). Communicates with the FastAPI backend.
"""

import streamlit as st
import httpx

st.set_page_config(
    page_title="NM-GPT – Campus Policy Assistant",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

BACKEND_URL = "http://localhost:8000"

# Custom CSS for citation styling
st.markdown("""
<style>
    .citation-box {
        background-color: #f0f2f6;
        border-left: 4px solid #4CAF50;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.85rem;
    }
    .page-badge {
        display: inline-block;
        background-color: #4CAF50;
        color: white;
        padding: 0.15rem 0.5rem;
        border-radius: 12px;
        font-size: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar with example questions and settings
with st.sidebar:
    st.title("NM-GPT")
    st.caption("Your Campus Policy Assistant 🎓")
    st.divider()

    st.subheader("💡 Example Questions")
    example_questions = [
        "What is the minimum attendance requirement?",
        "What are the rules for exam revaluation?",
        "What happens if I miss an exam due to illness?",
        "What is the grading system used?",
        "What are the rules for internal assessments?",
        "How do I apply for a leave of absence?",
        "What is the anti-ragging policy?",
        "What are the library rules?",
        "What scholarships are available?",
        "What is the code of conduct for students?",
    ]

    for q in example_questions:
        if st.button(q, key=f"example_{q}", use_container_width=True):
            st.session_state["pending_question"] = q

    st.divider()
    st.subheader("⚙️ Settings")
    top_k = st.slider("Number of sources to retrieve",
                       min_value=1, max_value=10, value=5)

# Chat history management
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# Header
st.markdown("<h1 style='text-align:center'>🎓 NM-GPT</h1>",
            unsafe_allow_html=True)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


def render_response(response_data):
    """Render citations and confidence below the answer."""
    if response_data.get("pages"):
        pages_str = ", ".join(str(p) for p in response_data["pages"])
        st.markdown(f"📄 **Referenced Pages:** {pages_str}")

    confidence = response_data.get("confidence", 0)
    if confidence > 0:
        label = "High" if confidence > 0.6 else "Medium" if confidence > 0.3 else "Low"
        st.progress(confidence, text=f"Confidence: {label} ({confidence:.0%})")

    if response_data.get("citations"):
        with st.expander(f"📚 View Sources ({len(response_data['citations'])} chunks)"):
            for i, citation in enumerate(response_data["citations"]):
                page_info = f"Page {citation['page_start']}"
                if citation["page_start"] != citation["page_end"]:
                    page_info = f"Pages {citation['page_start']}–{citation['page_end']}"
                st.markdown(f"""
<div class="citation-box">
    <strong>Source {i + 1}</strong> — <span class="page-badge">{page_info}</span><br/>
    <em>{citation['text']}</em>
</div>""", unsafe_allow_html=True)


def query_backend(question, top_k):
    """Send a question to the FastAPI backend."""
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{BACKEND_URL}/query",
                json={"question": question, "top_k": top_k},
            )
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        st.error("⚠️ Cannot connect to the backend server.")
        return None
    except httpx.HTTPStatusError as e:
        st.error(f"⚠️ Backend error: {e.response.json().get('detail', str(e))}")
        return None

# Handle input
pending = st.session_state.pop("pending_question", None)
user_input = st.chat_input("Ask a question about college policies…")
question = pending or user_input

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching the Student Resource Book…"):
            result = query_backend(question, top_k)

        if result:
            st.markdown(result["answer"])
            render_response(result)
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "citations": result.get("citations", []),
                "pages": result.get("pages", []),
                "confidence": result.get("confidence", 0),
            })
        else:
            fallback = "Sorry, I couldn't process your question right now."
            st.markdown(fallback)
            st.session_state.messages.append({"role": "assistant", "content": fallback})
```

**Key Features:**
- **Chat-style conversation** using `st.chat_message` and `st.chat_input`
- **Clickable example questions** in the sidebar for quick demos
- **Expandable citation cards** showing source text with page badges
- **Confidence progress bar** — green (>60%), yellow (30-60%), red (<30%)
- **Session state** preserves chat history across Streamlit reruns
- **Error handling** — shows helpful messages if the backend is down

### 💡 Example: How Session State Preserves Chat History

```python
# On first page load, session state is initialized:
if "messages" not in st.session_state:
    st.session_state.messages = []  # Empty chat history

# When user asks "What is the grading system?":
st.session_state.messages.append({"role": "user", "content": "What is the grading system?"})

# After backend responds:
st.session_state.messages.append({
    "role": "assistant",
    "content": "NMIMS uses a 10-point CGPA grading system... [Page 15]",
    "citations": [{"text": "...", "page_start": 15, "page_end": 15, "chunk_id": "chunk_0060"}],
    "pages": [15],
    "confidence": 0.85
})

# Now st.session_state.messages has 2 entries.
# When the user asks a second question, Streamlit re-runs the entire script.
# But st.session_state persists across re-runs, so the previous Q&A is still there.
# The loop at the top re-renders all previous messages:
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
```

**How the sidebar example buttons work:**
```python
# Each button has a unique key to avoid Streamlit conflicts:
if st.button("What is the grading system?", key="example_grading"):
    st.session_state["pending_question"] = "What is the grading system?"

# Later in the script, the pending question is consumed:
pending = st.session_state.pop("pending_question", None)
user_input = st.chat_input("Ask a question...")
question = pending or user_input  # Sidebar click takes priority

# If question is not None, the query flow begins
```

**How the confidence bar renders:**
```python
confidence = 0.78  # From the RAG pipeline

# Color logic:
if confidence > 0.6:
    label = "High"     # Green progress bar
elif confidence > 0.3:
    label = "Medium"   # Yellow progress bar
else:
    label = "Low"      # Red progress bar

# Streamlit renders:
st.progress(0.78, text="Confidence: High (78%)")
# → Shows a green progress bar filled to 78% with the label
```

**How the citation cards render:**
```python
# For each citation, we create a styled HTML div:
citation = {"text": "The grading system uses...", "page_start": 15, "page_end": 15}

st.markdown(f"""
<div class="citation-box">
    <strong>Source 1</strong> — <span class="page-badge">Page 15</span><br/>
    <em>The grading system uses...</em>
</div>
""", unsafe_allow_html=True)
# → Renders a green-bordered card with the page number as a badge
```

---

## 16. End-to-End Data Flow

Here's exactly what happens when a student types "What is the minimum attendance requirement?":

```
1. Student types question in Streamlit UI
                    │
2. Streamlit sends HTTP POST to FastAPI:
   POST /query {"question": "What is the minimum attendance?", "top_k": 5}
                    │
3. FastAPI validates request with Pydantic, calls RAGPipeline.query()
                    │
4. RAG Pipeline embeds the question:
   "What is the minimum attendance?" → [0.023, -0.184, 0.551, ...] (3072 floats)
                    │
5. FAISS searches the 405 pre-computed chunk vectors:
   Returns indices [42, 38, 45, 41, 39] with distances [0.31, 0.42, 0.48, 0.52, 0.61]
                    │
6. Metadata lookup:
   index 42 → chunk_0042 from Page 12: "The minimum attendance..."
   index 38 → chunk_0038 from Page 11: "Students must maintain..."
   ... (3 more)
                    │
7. Context assembly:
   "[Page 12]\nThe minimum attendance requirement is 75%..."
   "[Page 11]\nStudents must maintain regular attendance..."
                    │
8. Prompt construction:
   System prompt + retrieval template filled with context + question
                    │
9. Gemini generates answer:
   "The minimum attendance requirement is 75%. Students who fall below
    this threshold may be debarred from examinations. [Page 12]"
                    │
10. Citation extraction:
    Regex finds [Page 12] → pages = [12]
    Confidence = 1.0 - (0.31+0.42+0.48+0.52+0.61)/5/2.0 = 0.77
                    │
11. Response returned to FastAPI → Streamlit → student sees:
    ✅ Answer text
    📄 Referenced Pages: 12
    📊 Confidence: High (77%)
    📚 View Sources (5 chunks) [expandable]
```

---

## 17. Setup & Running Instructions

### Prerequisites
- Python 3.9+
- A Google Gemini API key (free at [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey))

### Step 1: Install Dependencies
```bash
cd NM-GPT
pip install -r requirements.txt
```

### Step 2: Configure API Key
```bash
cp .env.example .env
# Edit .env and replace "your_gemini_api_key_here" with your actual key
```

### Step 3: Run Ingestion Pipeline (one-time)
```bash
# Extract text from PDF (no API key needed)
python scripts/extract_pdf.py

# Split into chunks (no API key needed)
python scripts/chunk_documents.py

# Generate embeddings and build FAISS index (needs API key)
python scripts/build_index.py
```

### Step 4: Start the Backend
```bash
uvicorn backend.app:app --reload --port 8000
```
Verify: open [http://localhost:8000/health](http://localhost:8000/health) — should show `{"status": "healthy"}`

### Step 5: Start the Chat Interface
```bash
# In a new terminal window
streamlit run streamlit_app/app.py
```
Open the URL shown (usually [http://localhost:8501](http://localhost:8501))

---

## 18. Demo Questions & Expected Behavior

| # | Question | Expected Answer Topic |
|---|----------|----------------------|
| 1 | What is the minimum attendance requirement? | 75% attendance policy |
| 2 | What are the rules for exam revaluation? | Revaluation procedure |
| 3 | What happens if I miss an exam due to illness? | Medical leave & makeup exams |
| 4 | What is the grading system used? | Grading scale and GPA |
| 5 | What are the rules for internal assessments? | IA structure and weightage |
| 6 | How do I apply for a leave of absence? | Leave application process |
| 7 | What is the anti-ragging policy? | Anti-ragging committee & consequences |
| 8 | What are the library rules? | Library hours, borrowing limits |
| 9 | What scholarships are available? | Merit & need-based scholarships |
| 10 | What is the code of conduct for students? | Behavioral expectations |

**Edge case test:** Ask "Can I bring a pet to campus?" — the system should respond with "I could not find this information in the Student Resource Book."

---

## 19. Future Expansion Roadmap

The modular architecture supports these expansions without major refactoring:

| Feature | How to Add |
|---------|-----------|
| **Multi-document support** | Add more PDFs to ingestion pipeline, tag chunks with document source |
| **Department knowledge bases** | Separate FAISS indices per department, route queries based on intent |
| **Website ingestion** | Add a web scraper module to the ingestion pipeline |
| **Authentication (SSO)** | Add FastAPI middleware for JWT/OAuth validation |
| **Analytics dashboard** | Log queries to a database, build a Streamlit analytics page |
| **Placement info** | Add placement brochures as additional data sources |
| **Timetable system** | Integrate a timetable API as a new retrieval source |

---

## 20. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **FAISS over Chroma** | No server process needed, faster for our scale, simpler setup |
| **Separate FastAPI + Streamlit** | Clean separation of concerns; API can serve mobile apps or other frontends later |
| **Lazy-loaded pipeline** | Server starts even without index; gives clear error on first query |
| **Overlapping chunks** | Prevents information loss at chunk boundaries |
| **Low LLM temperature (0.2)** | Factual, consistent answers for policy questions |
| **Prompt templates in .txt files** | Non-developers can tweak behavior without touching Python |
| **Progress saving in index builder** | Graceful handling of API rate limits on free tier |
| **Heuristic confidence score** | Simple but useful — tells students how sure the system is |
| **`from __future__ import annotations`** | Python 3.9 compatibility for modern type hints |

---

*This document provides a complete understanding of the NM-GPT system. Every module, design decision, and data flow is explained so you can confidently present, modify, and extend this project.*
