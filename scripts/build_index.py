#!/usr/bin/env python3
from __future__ import annotations

"""
CollegeGPT – Build FAISS Index

Reads chunks from data/chunks.jsonl, generates embeddings via Gemini,
and builds a FAISS vector index.

Handles free-tier rate limits by:
  - Using small batch sizes (20 chunks)
  - Automatic retry with exponential backoff on 429 errors
  - Saving progress incrementally so interrupted runs can resume

Outputs:
  index/faiss_index.bin   – FAISS index file
  index/metadata.json     – chunk metadata (parallel to index vectors)

Usage:
    python scripts/build_index.py

Requires GOOGLE_API_KEY to be set in the environment or .env file.
"""

import json
import sys
import time
from pathlib import Path

# Allow imports from project root
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


def embed_batch_with_retry(batch: list[str], batch_num: int, total_batches: int) -> list[list[float]]:
    """Embed a batch of texts with retry logic for rate limits."""
    for attempt in range(MAX_RETRIES):
        try:
            return embed_texts(batch)
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                wait_time = BASE_DELAY * (2 ** attempt)  # Exponential backoff
                print(f"   ⏳ Rate limited on batch {batch_num}/{total_batches}. "
                      f"Waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})…")
                time.sleep(wait_time)
            else:
                raise  # Re-raise non-rate-limit errors
    raise RuntimeError(f"Failed to embed batch {batch_num} after {MAX_RETRIES} retries")


def build_index(chunks: list[dict]) -> tuple[faiss.IndexFlatL2, list[dict]]:
    """Generate embeddings and build FAISS index.

    Returns:
      (faiss_index, metadata_list)
    """
    texts = [c["text"] for c in chunks]

    # Check for saved progress
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

            # Save progress after each successful batch
            save_progress(all_embeddings)

            # Delay between batches to respect rate limits
            if i + BATCH_SIZE < len(texts):
                print(f"   💤 Cooling down for {BASE_DELAY}s…")
                time.sleep(BASE_DELAY)

    # Convert to numpy array
    embedding_matrix = np.array(all_embeddings, dtype=np.float32)
    dimension = embedding_matrix.shape[1]

    print(f"📐 Embedding dimension: {dimension}")
    print(f"📊 Total vectors: {embedding_matrix.shape[0]}")

    # Build FAISS index (flat L2 — exact search, fine for <10k vectors)
    index = faiss.IndexFlatL2(dimension)
    index.add(embedding_matrix)

    # Prepare metadata (parallel array to vectors)
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

    # Save index and metadata
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(FAISS_INDEX_PATH))
    print(f"💾 FAISS index saved to: {FAISS_INDEX_PATH}")

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"💾 Metadata saved to: {METADATA_PATH}")

    # Clean up progress file
    clear_progress()

    print("\n✅ Index built successfully!")
    print(f"   Vectors: {index.ntotal}")
    print(f"   Dimension: {index.d}")


if __name__ == "__main__":
    main()
