"""
Tests for backend/llm_client.py
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def patch_api_key(monkeypatch):
    monkeypatch.setattr("backend.llm_client.GOOGLE_API_KEY", "test-api-key-123")


# ── get_llm ───────────────────────────────────────────────────

def test_raises_when_api_key_empty(monkeypatch):
    monkeypatch.setattr("backend.llm_client.GOOGLE_API_KEY", "")
    from backend.llm_client import get_llm

    with pytest.raises(ValueError, match="GOOGLE_API_KEY is not set"):
        get_llm()


def test_passes_timeout_to_llm(monkeypatch):
    monkeypatch.setattr("backend.llm_client.LLM_TIMEOUT_SECONDS", 45)

    with patch("backend.llm_client.ChatGoogleGenerativeAI") as mock_cls:
        from backend.llm_client import get_llm
        get_llm()

    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs["timeout"] == 45


def test_passes_model_name(monkeypatch):
    monkeypatch.setattr("backend.llm_client.LLM_MODEL", "gemini-test-model")

    with patch("backend.llm_client.ChatGoogleGenerativeAI") as mock_cls:
        from backend.llm_client import get_llm
        get_llm()

    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs["model"] == "gemini-test-model"


def test_passes_temperature(monkeypatch):
    monkeypatch.setattr("backend.llm_client.LLM_TEMPERATURE", 0.2)

    with patch("backend.llm_client.ChatGoogleGenerativeAI") as mock_cls:
        from backend.llm_client import get_llm
        get_llm()

    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs["temperature"] == 0.2


def test_uses_rest_transport():
    with patch("backend.llm_client.ChatGoogleGenerativeAI") as mock_cls:
        from backend.llm_client import get_llm
        get_llm()

    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs.get("transport") == "rest"


# ── generate ─────────────────────────────────────────────────

def test_generate_returns_string():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "The attendance policy is 75%."

    with patch("backend.llm_client.get_llm", return_value=mock_llm):
        from backend.llm_client import generate
        result = generate("What is the attendance policy?")

    assert result == "The attendance policy is 75%."
    assert isinstance(result, str)


def test_generate_calls_invoke_with_prompt():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "answer"
    prompt = "System: Answer this. Question: test"

    with patch("backend.llm_client.get_llm", return_value=mock_llm):
        from backend.llm_client import generate
        generate(prompt)

    mock_llm.invoke.assert_called_once_with(prompt)


def test_generate_converts_content_to_str():
    """Ensure result is always a string even if content is not."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = 42  # non-string content

    with patch("backend.llm_client.get_llm", return_value=mock_llm):
        from backend.llm_client import generate
        result = generate("test")

    assert isinstance(result, str)
    assert result == "42"


# ── generate_stream ───────────────────────────────────────────

def test_generate_stream_yields_non_empty_tokens():
    chunks = [
        MagicMock(content="The minimum "),
        MagicMock(content="attendance is 75%."),
        MagicMock(content=""),   # empty chunk — should be skipped
        MagicMock(content=" [Page 12]"),
    ]
    mock_llm = MagicMock()
    mock_llm.stream.return_value = iter(chunks)

    with patch("backend.llm_client.get_llm", return_value=mock_llm):
        from backend.llm_client import generate_stream
        tokens = list(generate_stream("test prompt"))

    assert tokens == ["The minimum ", "attendance is 75%.", " [Page 12]"]


def test_generate_stream_skips_empty_content():
    chunks = [MagicMock(content=""), MagicMock(content=""), MagicMock(content="text")]
    mock_llm = MagicMock()
    mock_llm.stream.return_value = iter(chunks)

    with patch("backend.llm_client.get_llm", return_value=mock_llm):
        from backend.llm_client import generate_stream
        tokens = list(generate_stream("prompt"))

    assert tokens == ["text"]


def test_generate_stream_all_tokens_are_strings():
    chunks = [MagicMock(content="Hello"), MagicMock(content=" world")]
    mock_llm = MagicMock()
    mock_llm.stream.return_value = iter(chunks)

    with patch("backend.llm_client.get_llm", return_value=mock_llm):
        from backend.llm_client import generate_stream
        tokens = list(generate_stream("prompt"))

    assert all(isinstance(t, str) for t in tokens)


def test_generate_stream_yields_nothing_when_all_empty():
    chunks = [MagicMock(content=""), MagicMock(content="")]
    mock_llm = MagicMock()
    mock_llm.stream.return_value = iter(chunks)

    with patch("backend.llm_client.get_llm", return_value=mock_llm):
        from backend.llm_client import generate_stream
        tokens = list(generate_stream("prompt"))

    assert tokens == []
