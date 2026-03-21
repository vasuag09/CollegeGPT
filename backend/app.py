"""
NM-GPT – FastAPI Backend

Provides the REST API for the NM-GPT RAG system.

Endpoints:
  POST /query         – Answer a student question using the RAG pipeline
  POST /query/stream  – Stream answer tokens via Server-Sent Events
  GET  /health        – Health check

Usage:
  uvicorn backend.app:app --reload --port 8000
"""

import json
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.config import (
    ALLOWED_ORIGINS,
    DEFAULT_TOP_K,
    FAISS_INDEX_PATH,
    GOOGLE_API_KEY,
    MAX_QUESTION_LENGTH,
    METADATA_PATH,
)

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nmgpt.app")

# ── Rate Limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="NM-GPT API",
    description="Campus Policy AI Assistant – answers student questions using the Student Resource Book",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Lazy-load the RAG pipeline ──────────────────────────────
_pipeline = None


def get_pipeline():
    """Get or initialize the RAG pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        from backend.rag_pipeline import RAGPipeline
        logger.info("Initializing RAG pipeline...")
        _pipeline = RAGPipeline()
        logger.info("RAG pipeline ready")
    return _pipeline


# ── Request / Response Models ────────────────────────────────


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description="The student's question",
    )
    top_k: int = Field(
        default=DEFAULT_TOP_K, ge=1, le=20, description="Number of chunks to retrieve"
    )


class Citation(BaseModel):
    text: str
    page_start: int
    page_end: int
    chunk_id: str
    source: str = ""


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    pages: list[int]
    confidence: float


# ── Endpoints ────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    """Health check — verifies index files exist and API key is configured."""
    issues = []
    if not GOOGLE_API_KEY:
        issues.append("GOOGLE_API_KEY is not set")
    if not FAISS_INDEX_PATH.exists():
        issues.append(f"FAISS index not found at {FAISS_INDEX_PATH}")
    if not METADATA_PATH.exists():
        issues.append(f"Metadata not found at {METADATA_PATH}")

    if issues:
        logger.warning("Health check failed: %s", issues)
        raise HTTPException(status_code=503, detail={"status": "unhealthy", "issues": issues})

    return {"status": "healthy", "service": "NM-GPT"}


@app.post("/query", response_model=QueryResponse)
@limiter.limit("10/minute")
async def query(request: Request, body: QueryRequest):
    """Answer a student question using the RAG pipeline."""
    logger.info("Query: %r (top_k=%d)", body.question[:80], body.top_k)
    try:
        pipeline = get_pipeline()
        result = pipeline.query(question=body.question, top_k=body.top_k)
        logger.info(
            "Query answered: confidence=%.2f, pages=%s",
            result["confidence"],
            result["pages"],
        )
        return QueryResponse(**result)
    except FileNotFoundError as e:
        logger.error("Index not found: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        logger.error("Value error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in /query")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post("/query/stream")
@limiter.limit("10/minute")
async def query_stream(request: Request, body: QueryRequest):
    """Stream an answer to a student question via Server-Sent Events.

    Event types:
      data: {"type": "token", "content": "..."}      – answer tokens
      data: {"type": "citations", ...}                – citations + metadata
      data: {"type": "done"}                          – stream complete
      data: {"type": "error", "message": "..."}       – on failure
    """
    logger.info("Stream query: %r (top_k=%d)", body.question[:80], body.top_k)

    def event_generator():
        try:
            pipeline = get_pipeline()
            for event in pipeline.query_stream(
                question=body.question,
                top_k=body.top_k,
            ):
                yield f"data: {json.dumps(event)}\n\n"
            logger.info("Stream query completed")
        except FileNotFoundError as e:
            logger.error("Index not found during stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except ValueError as e:
            logger.error("Value error during stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except Exception as e:
            logger.exception("Unexpected error in /query/stream")
            yield f"data: {json.dumps({'type': 'error', 'message': f'An error occurred: {str(e)}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
