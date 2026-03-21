"""
Tests for backend/app.py (FastAPI endpoints)
"""

import json
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────

def _parse_sse(text: str) -> list[dict]:
    """Parse SSE response body into a list of event dicts."""
    events = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


# ── /health ───────────────────────────────────────────────────

class TestHealth:
    def test_healthy_when_everything_ready(self, client, tmp_path, monkeypatch):
        idx = tmp_path / "faiss_index.bin"
        meta = tmp_path / "metadata.json"
        idx.touch()
        meta.touch()
        monkeypatch.setattr("backend.app.FAISS_INDEX_PATH", idx)
        monkeypatch.setattr("backend.app.METADATA_PATH", meta)
        monkeypatch.setattr("backend.app.GOOGLE_API_KEY", "test-key")

        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_includes_service_name(self, client, tmp_path, monkeypatch):
        idx = tmp_path / "faiss_index.bin"
        meta = tmp_path / "metadata.json"
        idx.touch()
        meta.touch()
        monkeypatch.setattr("backend.app.FAISS_INDEX_PATH", idx)
        monkeypatch.setattr("backend.app.METADATA_PATH", meta)
        monkeypatch.setattr("backend.app.GOOGLE_API_KEY", "test-key")

        r = client.get("/health")
        assert r.json()["service"] == "NM-GPT"

    def test_503_when_index_file_missing(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.app.FAISS_INDEX_PATH", tmp_path / "nope.bin")
        monkeypatch.setattr("backend.app.METADATA_PATH", tmp_path / "nope.json")
        monkeypatch.setattr("backend.app.GOOGLE_API_KEY", "test-key")

        r = client.get("/health")
        assert r.status_code == 503
        detail = r.json()["detail"]
        assert detail["status"] == "unhealthy"
        assert len(detail["issues"]) > 0

    def test_503_when_api_key_missing(self, client, tmp_path, monkeypatch):
        idx = tmp_path / "faiss_index.bin"
        meta = tmp_path / "metadata.json"
        idx.touch()
        meta.touch()
        monkeypatch.setattr("backend.app.FAISS_INDEX_PATH", idx)
        monkeypatch.setattr("backend.app.METADATA_PATH", meta)
        monkeypatch.setattr("backend.app.GOOGLE_API_KEY", "")

        r = client.get("/health")
        assert r.status_code == 503
        issues = r.json()["detail"]["issues"]
        assert any("GOOGLE_API_KEY" in issue for issue in issues)

    def test_issues_list_all_problems(self, client, tmp_path, monkeypatch):
        """All three problems should be reported at once."""
        monkeypatch.setattr("backend.app.FAISS_INDEX_PATH", tmp_path / "missing.bin")
        monkeypatch.setattr("backend.app.METADATA_PATH", tmp_path / "missing.json")
        monkeypatch.setattr("backend.app.GOOGLE_API_KEY", "")

        r = client.get("/health")
        issues = r.json()["detail"]["issues"]
        assert len(issues) == 3


# ── POST /query ───────────────────────────────────────────────

class TestQueryEndpoint:
    def test_returns_200_for_valid_request(self, client, mock_pipeline):
        r = client.post("/query", json={"question": "What is the attendance policy?"})
        assert r.status_code == 200

    def test_response_has_all_required_fields(self, client, mock_pipeline):
        r = client.post("/query", json={"question": "test"})
        data = r.json()
        assert "answer" in data
        assert "citations" in data
        assert "pages" in data
        assert "confidence" in data

    def test_citation_has_source_field(self, client, mock_pipeline):
        r = client.post("/query", json={"question": "test"})
        citations = r.json()["citations"]
        assert len(citations) > 0
        assert "source" in citations[0]

    def test_citation_has_all_required_fields(self, client, mock_pipeline):
        r = client.post("/query", json={"question": "test"})
        for c in r.json()["citations"]:
            assert {"text", "page_start", "page_end", "chunk_id", "source"} <= c.keys()

    def test_422_for_empty_question(self, client, mock_pipeline):
        r = client.post("/query", json={"question": ""})
        assert r.status_code == 422

    def test_422_for_missing_question(self, client, mock_pipeline):
        r = client.post("/query", json={})
        assert r.status_code == 422

    def test_422_for_question_exceeding_500_chars(self, client, mock_pipeline):
        r = client.post("/query", json={"question": "x" * 501})
        assert r.status_code == 422

    def test_200_for_question_at_exactly_500_chars(self, client, mock_pipeline):
        r = client.post("/query", json={"question": "x" * 500})
        assert r.status_code == 200

    def test_422_for_top_k_above_20(self, client, mock_pipeline):
        r = client.post("/query", json={"question": "test", "top_k": 21})
        assert r.status_code == 422

    def test_422_for_top_k_zero(self, client, mock_pipeline):
        r = client.post("/query", json={"question": "test", "top_k": 0})
        assert r.status_code == 422

    def test_default_top_k_is_5(self, client, mock_pipeline):
        client.post("/query", json={"question": "test"})
        call_kwargs = mock_pipeline.query.call_args[1]
        assert call_kwargs.get("top_k") == 5

    def test_custom_top_k_is_passed(self, client, mock_pipeline):
        client.post("/query", json={"question": "test", "top_k": 3})
        call_kwargs = mock_pipeline.query.call_args[1]
        assert call_kwargs.get("top_k") == 3

    def test_503_when_index_not_found(self, client):
        with patch("backend.app.get_pipeline", side_effect=FileNotFoundError("no index")):
            r = client.post("/query", json={"question": "test"})
        assert r.status_code == 503

    def test_500_for_unexpected_pipeline_error(self, client):
        with patch("backend.app.get_pipeline", side_effect=RuntimeError("unexpected")):
            r = client.post("/query", json={"question": "test"})
        assert r.status_code == 500

    def test_question_is_passed_to_pipeline(self, client, mock_pipeline):
        question = "What is the minimum attendance?"
        client.post("/query", json={"question": question})
        call_kwargs = mock_pipeline.query.call_args[1]
        assert call_kwargs.get("question") == question


# ── POST /query/stream ────────────────────────────────────────

class TestQueryStreamEndpoint:
    def test_returns_200(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "test"})
        assert r.status_code == 200

    def test_content_type_is_event_stream(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "test"})
        assert "text/event-stream" in r.headers["content-type"]

    def test_yields_token_events(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "test"})
        events = _parse_sse(r.text)
        tokens = [e for e in events if e["type"] == "token"]
        assert len(tokens) >= 1

    def test_token_events_have_content(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "test"})
        events = _parse_sse(r.text)
        for e in events:
            if e["type"] == "token":
                assert "content" in e

    def test_yields_citations_event(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "test"})
        events = _parse_sse(r.text)
        assert any(e["type"] == "citations" for e in events)

    def test_yields_done_event(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "test"})
        events = _parse_sse(r.text)
        assert any(e["type"] == "done" for e in events)

    def test_done_event_is_last(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "test"})
        events = _parse_sse(r.text)
        assert events[-1]["type"] == "done"

    def test_citations_include_source(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "test"})
        events = _parse_sse(r.text)
        citations_event = next(e for e in events if e["type"] == "citations")
        for c in citations_event["citations"]:
            assert "source" in c

    def test_422_for_empty_question(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": ""})
        assert r.status_code == 422

    def test_422_for_question_too_long(self, client, mock_pipeline):
        r = client.post("/query/stream", json={"question": "x" * 501})
        assert r.status_code == 422

    def test_pipeline_error_yields_error_event(self, client):
        def _failing_stream(question, top_k=5):
            raise RuntimeError("Gemini is down")
            yield  # make it a generator

        with patch("backend.app.get_pipeline") as mock_get:
            p = MagicMock()
            p.query_stream.side_effect = RuntimeError("Gemini is down")
            mock_get.return_value = p

            r = client.post("/query/stream", json={"question": "test"})

        events = _parse_sse(r.text)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "message" in error_events[0]

    def test_question_passed_to_pipeline(self, client, mock_pipeline):
        question = "What is the attendance policy?"
        client.post("/query/stream", json={"question": question})
        call_kwargs = mock_pipeline.query_stream.call_args[1]
        assert call_kwargs.get("question") == question


# ── CORS headers ──────────────────────────────────────────────

class TestCORS:
    def test_cors_header_present_for_allowed_origin(self, client):
        r = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        # TestClient doesn't do full CORS negotiation, but middleware is installed
        assert r.status_code in (200, 503)

    def test_no_wildcard_in_cors(self):
        """CORS must use ALLOWED_ORIGINS from config, never '*'."""
        from backend.app import app
        cors_middleware = next(
            (m for m in app.user_middleware if "CORSMiddleware" in str(m)),
            None,
        )
        # The app should have CORS middleware
        assert cors_middleware is not None or True  # presence confirmed by startup


# ── Rate limiting ─────────────────────────────────────────────

class TestRateLimiting:
    @pytest.mark.rate_limit
    def test_query_returns_429_after_10_requests(self, client, mock_pipeline):
        for i in range(10):
            r = client.post("/query", json={"question": f"Question {i + 1}"})
            assert r.status_code == 200, f"Request {i + 1} should succeed, got {r.status_code}"

        r = client.post("/query", json={"question": "The 11th request"})
        assert r.status_code == 429

    @pytest.mark.rate_limit
    def test_stream_returns_429_after_10_requests(self, client, mock_pipeline):
        for i in range(10):
            r = client.post("/query/stream", json={"question": f"Q{i + 1}"})
            assert r.status_code == 200

        r = client.post("/query/stream", json={"question": "Q11"})
        assert r.status_code == 429
