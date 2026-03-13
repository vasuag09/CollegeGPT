from __future__ import annotations

"""
CollegeGPT – Embedding Wrapper

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
