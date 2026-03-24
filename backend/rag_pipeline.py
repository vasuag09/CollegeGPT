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
import logging
import re
from collections.abc import Generator

_GREETING_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|howdy|sup|yo|greetings|good\s*(morning|afternoon|evening|day)|what'?s\s*up)\W*\s*$",
    re.IGNORECASE,
)

_GREETING_RESPONSE = (
    "Hello! I'm NM-GPT, your NMIMS campus assistant. "
    "Ask me anything about attendance policies, exam rules, academic calendar, "
    "UFM penalties, or any other information from official university documents."
)

_REWRITE_PROMPT_TEMPLATE = """Given the following conversation history and the user's latest follow-up question, rewrite the follow-up question into a standalone question that can be understood without the history.
Do NOT answer the question, just reformulate it. If the question is already standalone, return it exactly as is.

CHAT HISTORY:
{history_str}

LATEST QUESTION: {question}

STANDALONE QUESTION:"""

import numpy as np
import faiss

from backend.config import (
    FAISS_INDEX_PATH,
    METADATA_PATH,
    PROMPTS_DIR,
    DEFAULT_TOP_K,
    PAPERS_REGISTRY_PATH,
)
from backend.embeddings import embed_query
from backend.llm_client import generate, generate_stream

logger = logging.getLogger("nmgpt.pipeline")

# ── PYQ detection ─────────────────────────────────────────────
_PYQ_RE = re.compile(
    r"\b(pyqs?|previous\s+year|question\s+papers?|past\s+papers?|exam\s+papers?|old\s+papers?)\b",
    re.IGNORECASE,
)
_PYQ_STOPWORDS = frozenset({
    "do", "you", "have", "any", "the", "a", "an", "for", "of", "in", "and",
    "or", "is", "are", "what", "where", "can", "i", "me", "get", "find",
    "show", "list", "please", "want", "need", "looking", "question", "paper",
    "papers", "pyq", "pyqs", "previous", "year", "past", "exam", "exams", "old",
})

_papers_cache: list[dict] | None = None


def _load_papers() -> list[dict]:
    global _papers_cache
    if _papers_cache is not None:
        return _papers_cache
    if not PAPERS_REGISTRY_PATH.exists():
        _papers_cache = []
        return _papers_cache
    with open(PAPERS_REGISTRY_PATH, "r", encoding="utf-8") as f:
        _papers_cache = json.load(f)
    logger.info("Loaded %d papers from registry", len(_papers_cache))
    return _papers_cache


def _search_papers(question: str) -> list[dict]:
    """Score papers by keyword overlap with the question. Returns top 20."""
    tokens = {t.upper() for t in re.findall(r"[a-zA-Z0-9]+", question)
              if t.lower() not in _PYQ_STOPWORDS and len(t) > 1}
    if not tokens:
        return _load_papers()[:20]

    scored = []
    for paper in _load_papers():
        target = " ".join(filter(None, [
            paper.get("subject", ""),
            paper.get("filename", ""),
            paper.get("branch", ""),
        ])).upper()
        score = sum(1 for t in tokens if t in target)
        if score > 0:
            scored.append((score, paper))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:20]]


def _format_pyq_response(question: str, papers: list[dict]) -> str:
    if not papers:
        return (
            "I don't have question papers for that subject yet. "
            "We're still uploading papers — check back soon, or ask about another subject!"
        )

    grouped: dict[str, list[dict]] = {}
    for p in papers:
        subject = p.get("subject") or p.get("filename", "Unknown")
        grouped.setdefault(subject, []).append(p)

    lines = ["Here are the question papers I found:\n"]
    for subject, items in grouped.items():
        lines.append(f"**{subject}**")
        for item in items:
            label_parts = [
                item.get("year", ""),
                item.get("semester", ""),
                item.get("branch", ""),
            ]
            label = " · ".join(p for p in label_parts if p) or item.get("filename", "Paper")
            url = item.get("drive_url", "")
            if url:
                lines.append(f"- [{label}]({url})")
            else:
                lines.append(f"- {label}")
        lines.append("")

    return "\n".join(lines).strip()


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for NM-GPT."""

    def __init__(self):
        """Load FAISS index, metadata, and prompt templates."""
        logger.info("Loading FAISS index from %s", FAISS_INDEX_PATH)
        if not FAISS_INDEX_PATH.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {FAISS_INDEX_PATH}. "
                "Run `python scripts/build_index.py` first."
            )
        self.index = faiss.read_index(str(FAISS_INDEX_PATH))

        logger.info("Loading chunk metadata from %s", METADATA_PATH)
        if not METADATA_PATH.exists():
            raise FileNotFoundError(
                f"Metadata not found at {METADATA_PATH}. "
                "Run `python scripts/build_index.py` first."
            )
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        logger.info("Loaded %d chunks into metadata", len(self.metadata))

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
        logger.info("Retrieving top-%d chunks for query: %r", top_k, query[:60])
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

        logger.info("Retrieved %d chunks (avg distance=%.3f)",
                    len(results),
                    sum(c["distance"] for c in results) / len(results) if results else 0)
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

    def _rewrite_query(self, question: str, history: list[dict] | None) -> str:
        """Rewrite the user's query into a standalone question using chat history."""
        if not history:
            return question
        history_str = "\n".join(f"{msg.get('role', 'user').capitalize()}: {msg.get('content', '')}" for msg in history[-4:])
        prompt = _REWRITE_PROMPT_TEMPLATE.format(history_str=history_str, question=question)
        logger.info("Rewriting query based on history...")
        rewritten = generate(prompt).strip()
        logger.info("Rewritten query: %r", rewritten)
        return rewritten

    def _build_prompt(self, context: str, question: str, history: list[dict] | None = None) -> str:
        """Build the full prompt from system prompt + retrieval template.

        Uses str.partition() to prevent cross-substitution: context containing
        {question} or question containing {context} are both inserted verbatim.
        """
        before_ctx, _, after_ctx = self.retrieval_prompt_template.partition("{context}")
        before_q, _, after_q = after_ctx.partition("{question}")
        
        if history:
            history_str = "\n".join(f"{msg.get('role', 'user').capitalize()}: {msg.get('content', '')}" for msg in history[-4:])
            q_block = f"CHAT HISTORY:\n{history_str}\n\nSTUDENT'S LATEST QUESTION: {question}"
        else:
            q_block = question

        retrieval_prompt = before_ctx + context + before_q + q_block + after_q
        return f"{self.system_prompt}\n\n{retrieval_prompt}"

    def _extract_page_citations(self, answer: str, chunks: list[dict]) -> list[int]:
        """Extract page numbers explicitly cited in the answer text."""
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

    def query(self, question: str, top_k: int = DEFAULT_TOP_K, history: list[dict] | None = None) -> dict:
        """Run the full RAG pipeline.

        Returns:
          {
            "answer": str,
            "citations": [{"text": str, "page_start": int, "page_end": int, "source": str}, ...],
            "pages": [int, ...],
            "confidence": float
          }
        """
        if _GREETING_PATTERNS.match(question):
            return {
                "answer": _GREETING_RESPONSE,
                "citations": [],
                "pages": [],
                "confidence": 1.0,
            }

        if _PYQ_RE.search(question):
            papers = _search_papers(question)
            return {
                "answer": _format_pyq_response(question, papers),
                "citations": [],
                "pages": [],
                "confidence": 1.0,
            }

        search_query = self._rewrite_query(question, history)
        chunks = self.retrieve(search_query, top_k=top_k)

        if not chunks:
            return {
                "answer": "I could not find relevant information in the Student Resource Book.",
                "citations": [],
                "pages": [],
                "confidence": 0.0,
            }

        context = self._assemble_context(chunks)
        prompt = self._build_prompt(context, question, history)

        logger.info("Generating answer...")
        answer = generate(prompt)

        pages = self._extract_page_citations(answer, chunks)
        confidence = self._compute_confidence(chunks)
        logger.info("Answer generated: %d pages cited, confidence=%.2f", len(pages), confidence)

        citations = [
            {
                "text": c["text"][:300] + ("…" if len(c["text"]) > 300 else ""),
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "chunk_id": c["chunk_id"],
                "source": c.get("source", ""),
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
        self, question: str, top_k: int = DEFAULT_TOP_K, history: list[dict] | None = None
    ) -> Generator[dict, None, None]:
        """Stream the RAG pipeline response.

        Yields SSE-friendly dicts:
          {"type": "token", "content": "..."}       – streamed answer tokens
          {"type": "citations", "citations": [...], "pages": [...], "confidence": float}
          {"type": "done"}                          – signals completion
          {"type": "error", "message": "..."}       – on failure
        """
        if _GREETING_PATTERNS.match(question):
            yield {"type": "token", "content": _GREETING_RESPONSE}
            yield {"type": "citations", "citations": [], "pages": [], "confidence": 1.0}
            yield {"type": "done"}
            return

        if _PYQ_RE.search(question):
            papers = _search_papers(question)
            yield {"type": "token", "content": _format_pyq_response(question, papers)}
            yield {"type": "citations", "citations": [], "pages": [], "confidence": 1.0}
            yield {"type": "done"}
            return

        search_query = self._rewrite_query(question, history)
        chunks = self.retrieve(search_query, top_k=top_k)

        if not chunks:
            yield {
                "type": "token",
                "content": "I could not find relevant information in the Student Resource Book.",
            }
            yield {"type": "citations", "citations": [], "pages": [], "confidence": 0.0}
            yield {"type": "done"}
            return

        context = self._assemble_context(chunks)
        prompt = self._build_prompt(context, question, history)

        logger.info("Streaming answer...")
        full_answer = ""
        for token in generate_stream(prompt):
            full_answer += token
            yield {"type": "token", "content": token}

        pages = self._extract_page_citations(full_answer, chunks)
        confidence = self._compute_confidence(chunks)
        logger.info("Stream complete: %d pages cited, confidence=%.2f", len(pages), confidence)

        citations = [
            {
                "text": c["text"][:300] + ("…" if len(c["text"]) > 300 else ""),
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "chunk_id": c["chunk_id"],
                "source": c.get("source", ""),
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
