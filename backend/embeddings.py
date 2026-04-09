from __future__ import annotations

"""
NM-GPT – Embedding Wrapper

Modular embedding interface using Google Gen AI embeddings.
Uses the google-genai SDK (v1 API endpoint) instead of google-generativeai (v1beta).
The model can be swapped by changing EMBEDDING_MODEL in config.py.
"""

import logging

from google import genai
from google.genai import types
from backend.config import GOOGLE_API_KEY, EMBEDDING_MODEL

logger = logging.getLogger("nmgpt.embeddings")

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return a configured Gen AI client (singleton)."""
    global _client
    if _client is None:
        if not GOOGLE_API_KEY:
            raise ValueError(
                "GOOGLE_API_KEY is not set. "
                "Create a .env file with your key (see .env.example)."
            )
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    client = get_client()
    logger.info("Embedding %d texts with model %s", len(texts), EMBEDDING_MODEL)
    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        return [e.values for e in result.embeddings]
    except Exception as e:
        logger.error("Error embedding texts: %s", e)
        raise RuntimeError(f"Error embedding texts: {e}")


def embed_query(query: str) -> list[float]:
    """Generate an embedding for a single query string."""
    client = get_client()
    logger.debug("Embedding query: %r", query[:60])
    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.error("Error embedding query: %s", e)
        raise RuntimeError(f"Error embedding query: {e}")
