"""
Shared pytest fixtures and configuration for NM-GPT backend tests.
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient


# ── Rate limit helpers ───────────────────────────────────────

def _clear_rate_limit_storage():
    """Clear in-memory rate limit tracking between tests."""
    from backend.app import limiter

    storage = limiter._storage
    for attr in ("storage", "_storage", "expirations", "events", "locks"):
        d = getattr(storage, attr, None)
        if isinstance(d, dict):
            d.clear()


@pytest.fixture(autouse=True)
def manage_rate_limiting(request):
    """
    Default: disable rate limiting so tests don't interfere with each other.
    Tests marked @pytest.mark.rate_limit use real limiting (storage cleared first).
    """
    from backend.app import limiter

    if request.node.get_closest_marker("rate_limit"):
        _clear_rate_limit_storage()
        limiter.enabled = True
        yield
        limiter.enabled = True  # restore in case a test modified it
    else:
        limiter.enabled = False
        yield
        limiter.enabled = True  # always restore


# ── FastAPI test client ──────────────────────────────────────

@pytest.fixture
def client():
    from backend.app import app
    return TestClient(app)


# ── Shared sample data ───────────────────────────────────────

SAMPLE_CITATION = {
    "text": "Students must maintain 75% attendance to be eligible for examinations.",
    "page_start": 12,
    "page_end": 12,
    "chunk_id": "chunk_0042",
    "source": "Student Resource Book",
}

SAMPLE_QUERY_RESULT = {
    "answer": "The minimum attendance requirement is 75%. [Page 12]",
    "citations": [SAMPLE_CITATION],
    "pages": [12],
    "confidence": 0.85,
}


# ── Mock pipeline fixture ────────────────────────────────────

@pytest.fixture
def mock_pipeline():
    """Patch backend.app.get_pipeline() with a controllable mock."""
    with patch("backend.app.get_pipeline") as mock_get:
        pipeline = MagicMock()
        pipeline.query.return_value = SAMPLE_QUERY_RESULT

        def _stream(question, top_k=5, history=None):
            yield {"type": "token", "content": "The minimum attendance requirement is 75%."}
            yield {"type": "token", "content": " [Page 12]"}
            yield {
                "type": "citations",
                "citations": [SAMPLE_CITATION],
                "pages": [12],
                "confidence": 0.85,
            }
            yield {"type": "done"}

        pipeline.query_stream.side_effect = _stream
        mock_get.return_value = pipeline
        yield pipeline


# ── Shared pipeline instance for unit tests ──────────────────

SAMPLE_METADATA = [
    {
        "chunk_id": "chunk_0001",
        "text": "Students must maintain 75% attendance to be eligible for examinations.",
        "page_start": 12,
        "page_end": 12,
        "source": "Student Resource Book",
    },
    {
        "chunk_id": "chunk_0002",
        "text": "The grading system uses a 10-point CGPA scale.",
        "page_start": 15,
        "page_end": 15,
        "source": "Student Resource Book",
    },
    {
        "chunk_id": "chunk_0003",
        "text": "UFM offences carry penalties from grade reduction to expulsion.",
        "page_start": 3,
        "page_end": 3,
        "source": "UFM Policy",
    },
    {
        "chunk_id": "chunk_0004",
        "text": "Exam halls open 30 minutes before the scheduled start.",
        "page_start": 1,
        "page_end": 1,
        "source": "TEE Instructions",
    },
    {
        "chunk_id": "chunk_0005",
        "text": "Students must produce their hall ticket and college ID before entry.",
        "page_start": 1,
        "page_end": 2,
        "source": "TEE Instructions",
    },
]

SYSTEM_PROMPT = "You are NM-GPT. Answer only from the context provided."
RETRIEVAL_TEMPLATE = "Context: {context}\n\nQuestion: {question}\n\nAnswer:"


@pytest.fixture
def pipeline():
    """
    RAGPipeline instance with all file I/O bypassed.
    Index search returns the first 5 SAMPLE_METADATA chunks.
    """
    from backend.rag_pipeline import RAGPipeline

    with patch.object(RAGPipeline, "__init__", lambda self: None):
        p = RAGPipeline()

    p.metadata = SAMPLE_METADATA
    p.system_prompt = SYSTEM_PROMPT
    p.retrieval_prompt_template = RETRIEVAL_TEMPLATE

    mock_index = MagicMock()
    mock_index.search.return_value = (
        np.array([[0.3, 0.5, 0.6, 0.7, 0.9]], dtype=np.float32),
        np.array([[0, 1, 2, 3, 4]], dtype=np.int64),
    )
    p.index = mock_index
    return p
