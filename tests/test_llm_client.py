"""
Tests for backend/llm_client.py
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Reset the singleton client and ensure a test API key is set."""
    monkeypatch.setattr("backend.llm_client._client", None)
    monkeypatch.setattr("backend.llm_client.GOOGLE_API_KEY", "test-api-key-123")


def _make_response(text: str) -> MagicMock:
    """Build a mock GenerateContentResponse with a single text part."""
    part = MagicMock()
    part.thought = False
    part.text = text
    candidate = MagicMock()
    candidate.content.parts = [part]
    response = MagicMock()
    response.candidates = [candidate]
    return response


# ── get_client ───────────────────────────────────────────────

def test_raises_when_api_key_empty(monkeypatch):
    monkeypatch.setattr("backend.llm_client.GOOGLE_API_KEY", "")
    from backend.llm_client import get_client

    with pytest.raises(ValueError, match="GOOGLE_API_KEY is not set"):
        get_client()


def test_get_client_passes_api_key():
    with patch("backend.llm_client.genai.Client") as mock_cls:
        from backend.llm_client import get_client
        get_client()

    mock_cls.assert_called_once_with(api_key="test-api-key-123")


def test_get_client_is_singleton():
    with patch("backend.llm_client.genai.Client") as mock_cls:
        from backend.llm_client import get_client
        get_client()
        get_client()

    mock_cls.assert_called_once()


# ── generate ─────────────────────────────────────────────────

def test_generate_returns_string():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_response("The attendance policy is 75%.")

    with patch("backend.llm_client.get_client", return_value=mock_client):
        from backend.llm_client import generate
        result = generate("What is the attendance policy?")

    assert result == "The attendance policy is 75%."
    assert isinstance(result, str)


def test_generate_calls_with_correct_prompt():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_response("answer")
    prompt = "System: Answer this. Question: test"

    with patch("backend.llm_client.get_client", return_value=mock_client):
        from backend.llm_client import generate
        generate(prompt)

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["contents"] == prompt


def test_generate_uses_configured_model(monkeypatch):
    monkeypatch.setattr("backend.llm_client.LLM_MODEL", "gemini-test-model")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_response("ok")

    with patch("backend.llm_client.get_client", return_value=mock_client):
        from backend.llm_client import generate
        generate("test")

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-test-model"


def test_generate_empty_text_returns_empty_string():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_response("")

    with patch("backend.llm_client.get_client", return_value=mock_client):
        from backend.llm_client import generate
        result = generate("test")

    assert isinstance(result, str)
    assert result == ""


# ── generate_stream ───────────────────────────────────────────

def test_generate_stream_yields_non_empty_tokens():
    chunks = [
        _make_response("The minimum "),
        _make_response("attendance is 75%."),
        _make_response(""),   # empty — should be skipped
        _make_response(" [Page 12]"),
    ]
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = iter(chunks)

    with patch("backend.llm_client.get_client", return_value=mock_client):
        from backend.llm_client import generate_stream
        tokens = list(generate_stream("test prompt"))

    assert tokens == ["The minimum ", "attendance is 75%.", " [Page 12]"]


def test_generate_stream_skips_empty_content():
    chunks = [_make_response(""), _make_response(""), _make_response("text")]
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = iter(chunks)

    with patch("backend.llm_client.get_client", return_value=mock_client):
        from backend.llm_client import generate_stream
        tokens = list(generate_stream("prompt"))

    assert tokens == ["text"]


def test_generate_stream_all_tokens_are_strings():
    chunks = [_make_response("Hello"), _make_response(" world")]
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = iter(chunks)

    with patch("backend.llm_client.get_client", return_value=mock_client):
        from backend.llm_client import generate_stream
        tokens = list(generate_stream("prompt"))

    assert all(isinstance(t, str) for t in tokens)


def test_generate_stream_yields_nothing_when_all_empty():
    chunks = [_make_response(""), _make_response("")]
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = iter(chunks)

    with patch("backend.llm_client.get_client", return_value=mock_client):
        from backend.llm_client import generate_stream
        tokens = list(generate_stream("prompt"))

    assert tokens == []
