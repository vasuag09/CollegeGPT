"""
Tests for backend/embeddings.py
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def patch_api_key(monkeypatch):
    """Provide a fake API key for all embedding tests."""
    monkeypatch.setattr("backend.embeddings.GOOGLE_API_KEY", "test-api-key-123")


# ── get_embedding_model ──────────────────────────────────────

def test_raises_when_api_key_empty(monkeypatch):
    monkeypatch.setattr("backend.embeddings.GOOGLE_API_KEY", "")
    from backend.embeddings import get_embedding_model

    with pytest.raises(ValueError, match="GOOGLE_API_KEY is not set"):
        get_embedding_model()


def test_configures_genai_with_key():
    mock_genai = MagicMock()
    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import get_embedding_model
        get_embedding_model()

    mock_genai.configure.assert_called_once()
    call_kwargs = mock_genai.configure.call_args[1]
    assert call_kwargs["api_key"] == "test-api-key-123"


def test_configures_genai_with_rest_transport():
    mock_genai = MagicMock()
    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import get_embedding_model
        get_embedding_model()

    call_kwargs = mock_genai.configure.call_args[1]
    assert call_kwargs.get("transport") == "rest"


# ── embed_query ──────────────────────────────────────────────

def test_embed_query_returns_list_of_floats():
    mock_genai = MagicMock()
    mock_genai.embed_content.return_value = {"embedding": [0.1] * 3072}

    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import embed_query
        result = embed_query("What is the attendance policy?")

    assert isinstance(result, list)
    assert len(result) == 3072
    assert all(isinstance(v, float) for v in result)


def test_embed_query_uses_retrieval_query_task():
    mock_genai = MagicMock()
    mock_genai.embed_content.return_value = {"embedding": [0.1] * 3072}

    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import embed_query
        embed_query("test query")

    call_kwargs = mock_genai.embed_content.call_args[1]
    assert call_kwargs.get("task_type") == "retrieval_query"


def test_embed_query_passes_text_to_api():
    mock_genai = MagicMock()
    mock_genai.embed_content.return_value = {"embedding": [0.1] * 3072}
    question = "What is the minimum attendance?"

    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import embed_query
        embed_query(question)

    call_kwargs = mock_genai.embed_content.call_args[1]
    assert call_kwargs.get("content") == question


def test_embed_query_raises_runtime_error_on_api_failure():
    mock_genai = MagicMock()
    mock_genai.embed_content.side_effect = Exception("API quota exceeded")

    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import embed_query
        with pytest.raises(RuntimeError, match="Error embedding query"):
            embed_query("test question")


# ── embed_texts ──────────────────────────────────────────────

def test_embed_texts_returns_list_of_lists():
    mock_genai = MagicMock()
    mock_genai.embed_content.return_value = {"embedding": [[0.1] * 3072, [0.2] * 3072]}

    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import embed_texts
        result = embed_texts(["text one", "text two"])

    assert isinstance(result, list)
    assert len(result) == 2
    assert len(result[0]) == 3072


def test_embed_texts_uses_retrieval_document_task():
    mock_genai = MagicMock()
    mock_genai.embed_content.return_value = {"embedding": [[0.1] * 3072]}

    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import embed_texts
        embed_texts(["sample document text"])

    call_kwargs = mock_genai.embed_content.call_args[1]
    assert call_kwargs.get("task_type") == "retrieval_document"


def test_embed_texts_passes_all_texts_to_api():
    mock_genai = MagicMock()
    mock_genai.embed_content.return_value = {"embedding": [[0.1] * 3072, [0.2] * 3072]}
    texts = ["first document", "second document"]

    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import embed_texts
        embed_texts(texts)

    call_kwargs = mock_genai.embed_content.call_args[1]
    assert call_kwargs.get("content") == texts


def test_embed_texts_raises_runtime_error_on_api_failure():
    mock_genai = MagicMock()
    mock_genai.embed_content.side_effect = Exception("Network error")

    with patch("backend.embeddings.genai", mock_genai):
        from backend.embeddings import embed_texts
        with pytest.raises(RuntimeError, match="Error embedding texts"):
            embed_texts(["text1", "text2"])
