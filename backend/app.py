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

import asyncio
import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from twilio.twiml.messaging_response import MessagingResponse

from backend.config import (
    ADMIN_PASSWORD,
    ALLOWED_ORIGINS,
    DEFAULT_TOP_K,
    FAISS_INDEX_PATH,
    GOOGLE_API_KEY,
    MAX_QUESTION_LENGTH,
    METADATA_PATH,
    SUPABASE_KEY,
    SUPABASE_URL,
)
from backend.query_logger import log_query

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
    allow_headers=["Content-Type", "X-Admin-Password"],
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


class Message(BaseModel):
    role: str
    content: str


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
    history: list[Message] = Field(
        default_factory=list, description="Recent conversation history"
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
    ui_action: Optional[str] = None


class AttendanceRequest(BaseModel):
    sap_id: str = Field(..., min_length=1, max_length=30)
    sap_password: str = Field(..., min_length=1, max_length=100)
    year_key: Optional[str] = None
    semester_label: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AttendanceOptionsRequest(BaseModel):
    sap_id: str = Field(..., min_length=1, max_length=30)
    sap_password: str = Field(..., min_length=1, max_length=100)


class CourseHoursRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    total_hours: int = Field(..., ge=1, le=500)


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


def _answer_type(result: dict) -> str:
    """Classify a query result for analytics."""
    answer = result.get("answer", "")
    if not result.get("citations") and "question paper" in answer.lower():
        return "pyq"
    if not result.get("citations") and result.get("confidence") == 1.0:
        return "greeting"
    if result.get("citations"):
        return "rag"
    return "rag"


@app.post("/query", response_model=QueryResponse)
@limiter.limit("10/minute")
async def query(request: Request, body: QueryRequest):
    """Answer a student question using the RAG pipeline."""
    logger.info("Query: %r (top_k=%d)", body.question[:80], body.top_k)
    start = time.time()
    try:
        pipeline = get_pipeline()
        history = [msg.model_dump() for msg in body.history]
        result = pipeline.query(question=body.question, top_k=body.top_k, history=history)
        latency = int((time.time() - start) * 1000)
        logger.info("Query answered: confidence=%.2f, pages=%s", result["confidence"], result["pages"])
        log_query(body.question, _answer_type(result), result["confidence"], latency, get_remote_address(request))
        return QueryResponse(**result)
    except FileNotFoundError as e:
        log_query(body.question, "error", 0.0, int((time.time() - start) * 1000), get_remote_address(request))
        logger.error("Index not found: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        log_query(body.question, "error", 0.0, int((time.time() - start) * 1000), get_remote_address(request))
        logger.error("Value error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log_query(body.question, "error", 0.0, int((time.time() - start) * 1000), get_remote_address(request))
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
    start = time.time()
    ip = get_remote_address(request)

    def event_generator():
        _log = {"type": "rag", "confidence": 0.0}
        try:
            pipeline = get_pipeline()
            history = [msg.model_dump() for msg in body.history]
            for event in pipeline.query_stream(question=body.question, top_k=body.top_k, history=history):
                if event.get("type") == "action":
                    _log["type"] = "action"
                if event.get("type") == "citations":
                    _log["confidence"] = event.get("confidence", 0.0)
                    has_citations = bool(event.get("citations"))
                    answer_is_pyq = not has_citations and "question paper" in event.get("answer", "").lower()
                    if not has_citations and _log["confidence"] == 1.0 and not answer_is_pyq:
                        _log["type"] = "greeting"
                    elif not has_citations:
                        _log["type"] = "pyq"
                if event.get("type") == "done":
                    log_query(body.question, _log["type"], _log["confidence"], int((time.time() - start) * 1000), ip)
                yield f"data: {json.dumps(event)}\n\n"
            logger.info("Stream query completed")
        except FileNotFoundError as e:
            log_query(body.question, "error", 0.0, int((time.time() - start) * 1000), ip)
            logger.error("Index not found during stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except ValueError as e:
            log_query(body.question, "error", 0.0, int((time.time() - start) * 1000), ip)
            logger.error("Value error during stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except Exception as e:
            log_query(body.question, "error", 0.0, int((time.time() - start) * 1000), ip)
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


# ── Twilio WhatsApp Webhook ──────────────────────────────────

whatsapp_sessions: dict[str, list[dict]] = {}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...)
):
    """Handle incoming WhatsApp messages from Twilio."""
    question = Body.strip()
    pipeline = get_pipeline()
    
    try:
        history = whatsapp_sessions.get(From, [])
        result = pipeline.query(question=question, top_k=5, history=history)
        answer = result["answer"]
        
        if result["citations"]:
            citations_text = ", ".join(set([c["source"] for c in result["citations"]]))
            reply_text = f"{answer}\n\n*Source:* {citations_text}"
        else:
            reply_text = answer

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})
        whatsapp_sessions[From] = history[-6:]
    except Exception as e:
        logger.error("Error in whatsapp_webhook: %r", e)
        reply_text = "I'm currently unable to access my knowledge base. Please try again later."
    
    twiml = MessagingResponse()
    twiml.message(reply_text)
    
    return Response(content=str(twiml), media_type="application/xml")


# ── Attendance ───────────────────────────────────────────────

@app.post("/attendance")
@limiter.limit("5/minute")
async def get_attendance(request: Request, body: AttendanceRequest):
    """Fetch student attendance from the SAP NetWeaver portal.

    Credentials are used immediately and never stored or logged.
    Returns subject-wise attendance percentages.
    """
    logger.info("Attendance fetch for sap_id=%s***", body.sap_id[:4])
    from scripts.attendance_scraper import fetch_attendance
    from backend.query_logger import log_query
    loop = asyncio.get_event_loop()
    t0 = time.time()
    try:
        subjects = await loop.run_in_executor(
            None, fetch_attendance,
            body.sap_id, body.sap_password,
            body.year_key, body.semester_label,
            body.start_date, body.end_date,
        )
        log_query(
            question="[Attendance fetch]",
            answer_type="attendance",
            confidence=1.0,
            latency_ms=int((time.time() - t0) * 1000),
            ip=get_remote_address(request),
        )
        return {"subjects": subjects, "error": None}
    except RuntimeError as e:
        return {"subjects": [], "error": str(e)}
    except Exception as e:
        logger.exception("Unexpected error in /attendance")
        return {"subjects": [], "error": "An unexpected error occurred. Please try again."}


@app.post("/attendance/course-hours")
async def save_course_hours(body: CourseHoursRequest):
    """Persist manually entered course hours to Supabase (upsert by course name).

    Uses an upsert so repeated saves for the same subject just update the row.
    Falls back silently if Supabase is not configured.
    """
    import httpx
    from backend.config import SUPABASE_KEY, SUPABASE_URL

    course = body.subject.strip()

    if SUPABASE_URL and SUPABASE_KEY:
        url = f"{SUPABASE_URL}/rest/v1/course_hours"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        payload = {"course": course, "total_hours": body.total_hours}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(url, json=payload, headers=headers)
        except Exception as exc:
            logger.warning("Supabase upsert failed for course_hours: %s", exc)
            return {"ok": False, "error": "Could not save — database unavailable."}

    logger.info("Course hours saved: %s = %d hrs", course, body.total_hours)
    return {"ok": True}


@app.post("/attendance/options")
@limiter.limit("10/minute")
async def get_attendance_options(request: Request, body: AttendanceOptionsRequest):
    """Fetch available academic years and semesters for the student.

    Called before /attendance to populate the year/semester selectors in the UI.
    """
    logger.info("Attendance options fetch for sap_id=%s***", body.sap_id[:4])
    from scripts.attendance_scraper import fetch_attendance_options
    loop = asyncio.get_event_loop()
    try:
        options = await loop.run_in_executor(
            None, fetch_attendance_options, body.sap_id, body.sap_password
        )
        return {"options": options, "error": None}
    except RuntimeError as e:
        return {"options": None, "error": str(e)}
    except Exception:
        logger.exception("Unexpected error in /attendance/options")
        return {"options": None, "error": "An unexpected error occurred. Please try again."}


# ── Admin Dashboard ──────────────────────────────────────────

@app.get("/admin/stats")
async def admin_stats(x_admin_password: str = Header(default="")):
    """Return aggregated query analytics from Supabase. Protected by ADMIN_PASSWORD."""
    if not ADMIN_PASSWORD or x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    # Fetch last 7 days of logs from Supabase
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    url = f"{SUPABASE_URL}/rest/v1/query_logs"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    params = {
        "select": "created_at,question,answer_type,confidence,latency_ms",
        "created_at": f"gte.{since}",
        "order": "created_at.desc",
        "limit": "2000",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as e:
        logger.error("Supabase fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch logs from Supabase")

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    total_all = len(rows)
    total_today = sum(
        1 for r in rows
        if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= today_start
    )
    total_week = total_all  # rows are already limited to 7 days

    # Answer type breakdown
    type_counts: Counter = Counter(r.get("answer_type", "rag") for r in rows)

    # Average confidence (rag only)
    rag_rows = [r for r in rows if r.get("answer_type") == "rag" and r.get("confidence") is not None]
    avg_confidence = round(sum(r["confidence"] for r in rag_rows) / len(rag_rows), 2) if rag_rows else 0.0

    # Average latency
    lat_rows = [r for r in rows if r.get("latency_ms") is not None]
    avg_latency = int(sum(r["latency_ms"] for r in lat_rows) / len(lat_rows)) if lat_rows else 0

    # Hourly counts (last 24h)
    hourly: dict[str, int] = defaultdict(int)
    cutoff_24h = now - timedelta(hours=24)
    for r in rows:
        ts = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        if ts >= cutoff_24h:
            hour_label = ts.strftime("%H:00")
            hourly[hour_label] += 1
    # Build ordered list for last 24 hours
    hourly_list = []
    for h in range(24):
        ts = cutoff_24h + timedelta(hours=h + 1)
        label = ts.strftime("%H:00")
        hourly_list.append({"hour": label, "count": hourly.get(label, 0)})

    # Top 10 questions (deduplicate by exact match)
    q_counter: Counter = Counter(r["question"] for r in rows if r.get("question"))
    top_questions = [
        {"question": q[:120], "count": c}
        for q, c in q_counter.most_common(10)
    ]

    return {
        "totals": {
            "today": total_today,
            "week": total_week,
            "all_time": total_all,
        },
        "answer_types": dict(type_counts),
        "avg_confidence": avg_confidence,
        "avg_latency_ms": avg_latency,
        "hourly": hourly_list,
        "top_questions": top_questions,
    }
