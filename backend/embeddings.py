from __future__ import annotations

"""
NM-GPT – Embedding Wrapper

Modular embedding interface using Google Generative AI embeddings.
The model can be swapped by changing EMBEDDING_MODEL in config.py.
"""

import logging

import google.generativeai as genai
from backend.config import GOOGLE_API_KEY, EMBEDDING_MODEL

logger = logging.getLogger("nmgpt.embeddings")


def get_embedding_model():
    """Configure and return the generative AI SDK."""
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY is not set. "
            "Create a .env file with your key (see .env.example)."
        )
    # Configure globally with REST transport to bypass gRPC DNS issues
    genai.configure(api_key=GOOGLE_API_KEY, transport='rest')
    return genai


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    get_embedding_model()
    logger.info("Embedding %d texts with model %s", len(texts), EMBEDDING_MODEL)
    try:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=texts,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        logger.error("Error embedding texts: %s", e)
        raise RuntimeError(f"Error embedding texts: {e}")


def embed_query(query: str) -> list[float]:
    """Generate an embedding for a single query string."""
    get_embedding_model()
    logger.debug("Embedding query: %r", query[:60])
    try:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=query,
            task_type="retrieval_query"
        )
        return result['embedding']
    except Exception as e:
        logger.error("Error embedding query: %s", e)
        raise RuntimeError(f"Error embedding query: {e}")
