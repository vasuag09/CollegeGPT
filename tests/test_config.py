"""
Tests for backend/config.py
"""

from pathlib import Path

import pytest


def test_max_question_length():
    from backend.config import MAX_QUESTION_LENGTH
    assert MAX_QUESTION_LENGTH == 500


def test_llm_timeout_is_positive_int():
    from backend.config import LLM_TIMEOUT_SECONDS
    assert isinstance(LLM_TIMEOUT_SECONDS, int)
    assert LLM_TIMEOUT_SECONDS > 0


def test_llm_timeout_default_is_60(monkeypatch):
    """Default timeout should be 60 seconds when env var is not set."""
    import importlib
    import backend.config as cfg

    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    importlib.reload(cfg)
    assert cfg.LLM_TIMEOUT_SECONDS == 60


def test_llm_timeout_reads_from_env(monkeypatch):
    import importlib
    import backend.config as cfg

    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "120")
    importlib.reload(cfg)
    assert cfg.LLM_TIMEOUT_SECONDS == 120


def test_allowed_origins_is_list():
    from backend.config import ALLOWED_ORIGINS
    assert isinstance(ALLOWED_ORIGINS, list)
    assert len(ALLOWED_ORIGINS) >= 1


def test_allowed_origins_default_includes_localhost(monkeypatch):
    import importlib
    import backend.config as cfg

    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    importlib.reload(cfg)
    assert any("localhost:3000" in o for o in cfg.ALLOWED_ORIGINS)


def test_allowed_origins_reads_from_env(monkeypatch):
    import importlib
    import backend.config as cfg

    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.com,https://app.example.com")
    importlib.reload(cfg)
    assert cfg.ALLOWED_ORIGINS == ["https://example.com", "https://app.example.com"]


def test_allowed_origins_strips_whitespace(monkeypatch):
    import importlib
    import backend.config as cfg

    monkeypatch.setenv("ALLOWED_ORIGINS", "  https://a.com  ,  https://b.com  ")
    importlib.reload(cfg)
    assert cfg.ALLOWED_ORIGINS == ["https://a.com", "https://b.com"]


def test_all_paths_are_path_instances():
    from backend.config import (
        CHUNKS_PATH,
        DATA_DIR,
        DOCS_DIR,
        FAISS_INDEX_PATH,
        INDEX_DIR,
        METADATA_PATH,
        PROJECT_ROOT,
        PROMPTS_DIR,
    )

    for p in [
        PROJECT_ROOT, DATA_DIR, INDEX_DIR, DOCS_DIR,
        CHUNKS_PATH, FAISS_INDEX_PATH, METADATA_PATH, PROMPTS_DIR,
    ]:
        assert isinstance(p, Path), f"{p!r} should be a Path"


def test_faiss_index_path_under_index_dir():
    from backend.config import FAISS_INDEX_PATH, INDEX_DIR
    assert str(FAISS_INDEX_PATH).startswith(str(INDEX_DIR))


def test_metadata_path_under_index_dir():
    from backend.config import METADATA_PATH, INDEX_DIR
    assert str(METADATA_PATH).startswith(str(INDEX_DIR))


def test_default_top_k_is_positive():
    from backend.config import DEFAULT_TOP_K
    assert DEFAULT_TOP_K > 0


def test_chunk_size_greater_than_chunk_overlap():
    from backend.config import CHUNK_OVERLAP, CHUNK_SIZE
    assert CHUNK_SIZE > CHUNK_OVERLAP > 0


def test_llm_temperature_in_valid_range():
    from backend.config import LLM_TEMPERATURE
    assert 0.0 <= LLM_TEMPERATURE <= 1.0


def test_llm_model_is_gemini():
    from backend.config import LLM_MODEL
    assert "gemini" in LLM_MODEL.lower()


def test_embedding_model_is_set():
    from backend.config import EMBEDDING_MODEL
    assert EMBEDDING_MODEL
    assert "embedding" in EMBEDDING_MODEL.lower()
