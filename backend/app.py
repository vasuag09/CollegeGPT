from __future__ import annotations

"""
CollegeGPT – FastAPI Backend

Provides the REST API for the CollegeGPT RAG system.

Endpoints:
  POST /query  – Answer a student question using the RAG pipeline
  GET  /health – Health check

Usage:
  uvicorn backend.app:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import DEFAULT_TOP_K

app = FastAPI(
    title="CollegeGPT API",
    description="Campus Policy AI Assistant – answers student questions using the Student Resource Book",
    version="1.0.0",
)

# Allow CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lazy-load the RAG pipeline ──────────────────────────────
# Loaded on first request to avoid startup failures when index is missing
_pipeline = None


def get_pipeline():
    """Get or initialize the RAG pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        from backend.rag_pipeline import RAGPipeline
        _pipeline = RAGPipeline()
    return _pipeline


# ── Request / Response Models ────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The student's question")
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=20, description="Number of chunks to retrieve")


class Citation(BaseModel):
    text: str
    page_start: int
    page_end: int
    chunk_id: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    pages: list[int]
    confidence: float


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "CollegeGPT"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a student question using the RAG pipeline.

    1. Embeds the question
    2. Retrieves relevant SRB chunks
    3. Generates an answer via Gemini
    4. Returns the answer with citations
    """
    try:
        pipeline = get_pipeline()
        result = pipeline.query(
            question=request.question,
            top_k=request.top_k,
        )
        return QueryResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}",
        )
