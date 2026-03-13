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
from collections.abc import Generator

import numpy as np
import faiss

from pathlib import Path

from backend.config import (
    FAISS_INDEX_PATH,
    METADATA_PATH,
    PROMPTS_DIR,
    DEFAULT_TOP_K,
)
from backend.embeddings import embed_query
from backend.llm_client import generate, generate_stream


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for NM-GPT."""

    def __init__(self):
        """Load FAISS index, metadata, and prompt templates."""
        # Load FAISS index
        if not FAISS_INDEX_PATH.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {FAISS_INDEX_PATH}. "
                "Run `python scripts/build_index.py` first."
            )
        self.index = faiss.read_index(str(FAISS_INDEX_PATH))

        # Load chunk metadata
        if not METADATA_PATH.exists():
            raise FileNotFoundError(
                f"Metadata not found at {METADATA_PATH}. "
                "Run `python scripts/build_index.py` first."
            )
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        # Load prompt templates
        self.system_prompt = self._load_prompt("system_prompt.txt")
        self.retrieval_prompt_template = self._load_prompt("retrieval_prompt.txt")

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt template from the prompts directory."""
        path = PROMPTS_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def retrieve(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
        """Embed query and retrieve the top-k most relevant chunks.

        Returns list of dicts with keys:
          text, page_start, page_end, source, chunk_id, distance
        """
        query_embedding = embed_query(query)
        query_vector = np.array([query_embedding], dtype=np.float32)

        distances, indices = self.index.search(query_vector, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for empty slots
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
            context=context,
            question=question,
        )
        return f"{self.system_prompt}\n\n{retrieval_prompt}"

    def _extract_page_citations(self, answer: str, chunks: list[dict]) -> list[int]:
        """Extract page numbers cited in the answer text."""
        # Find explicit [Page X] or [Pages X-Y] citations
        page_pattern = r"\[Pages?\s*(\d+)(?:\s*[-–]\s*(\d+))?\]"
        matches = re.findall(page_pattern, answer)

        pages = set()
        for match in matches:
            start_page = int(match[0])
            pages.add(start_page)
            if match[1]:
                end_page = int(match[1])
                for p in range(start_page, end_page + 1):
                    pages.add(p)

        # If no explicit citations found, use pages from retrieved chunks
        if not pages:
            for chunk in chunks:
                for p in range(chunk["page_start"], chunk["page_end"] + 1):
                    pages.add(p)

        return sorted(pages)

    def _compute_confidence(self, chunks: list[dict]) -> float:
        """Compute a heuristic confidence score based on retrieval distances.

        Lower distance = better match = higher confidence.
        Returns a value between 0.0 and 1.0.
        """
        if not chunks:
            return 0.0

        distances = [c["distance"] for c in chunks]
        avg_distance = sum(distances) / len(distances)

        # Heuristic: map average L2 distance to confidence
        # Typical L2 distances for Gemini embeddings range ~0.3 to ~2.0
        # Lower is better
        confidence = max(0.0, min(1.0, 1.0 - (avg_distance / 2.0)))
        return round(confidence, 2)

    def query(self, question: str, top_k: int = DEFAULT_TOP_K) -> dict:
        """Run the full RAG pipeline.

        Returns:
          {
            "answer": str,
            "citations": [{"text": str, "page_start": int, "page_end": int}, ...],
            "pages": [int, ...],
            "confidence": float
          }
        """
        # Step 1-2: Retrieve relevant chunks
        chunks = self.retrieve(question, top_k=top_k)

        if not chunks:
            return {
                "answer": "I could not find relevant information in the Student Resource Book.",
                "citations": [],
                "pages": [],
                "confidence": 0.0,
            }

        # Step 3: Assemble context
        context = self._assemble_context(chunks)

        # Step 4: Build prompt
        prompt = self._build_prompt(context, question)

        # Step 5: Generate answer
        answer = generate(prompt)

        # Step 6: Extract citations and compute confidence
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

    def query_stream(
        self, question: str, top_k: int = DEFAULT_TOP_K
    ) -> Generator[dict, None, None]:
        """Stream the RAG pipeline response.

        Yields SSE-friendly dicts:
          {"type": "token", "content": "..."}       – streamed answer tokens
          {"type": "citations", "citations": [...], "pages": [...], "confidence": float}
          {"type": "done"}                          – signals completion
          {"type": "error", "message": "..."}       – on failure
        """
        # Step 1-2: Retrieve relevant chunks (synchronous, fast)
        chunks = self.retrieve(question, top_k=top_k)

        if not chunks:
            yield {
                "type": "token",
                "content": "I could not find relevant information in the Student Resource Book.",
            }
            yield {"type": "citations", "citations": [], "pages": [], "confidence": 0.0}
            yield {"type": "done"}
            return

        # Step 3-4: Assemble context and build prompt
        context = self._assemble_context(chunks)
        prompt = self._build_prompt(context, question)

        # Step 5: Stream the answer
        full_answer = ""
        for token in generate_stream(prompt):
            full_answer += token
            yield {"type": "token", "content": token}

        # Step 6: After streaming completes, send citations
        pages = self._extract_page_citations(full_answer, chunks)
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

        yield {
            "type": "citations",
            "citations": citations,
            "pages": pages,
            "confidence": confidence,
        }
        yield {"type": "done"}
