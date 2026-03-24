"""
NM-GPT – Query Logger

Logs each query to Supabase in a background daemon thread.
Never raises — logging must not affect the user response.

Table schema (run once in Supabase SQL editor):

    create table query_logs (
      id          bigserial primary key,
      created_at  timestamptz default now(),
      question    text not null,
      answer_type text,
      confidence  float,
      latency_ms  int,
      ip_hash     text
    );

    -- Allow anon key to insert (logging) but not read (dashboard uses service key)
    alter table query_logs enable row level security;
    create policy "insert_only" on query_logs for insert with check (true);
"""

import hashlib
import logging
import threading

import httpx

from backend.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger("nmgpt.query_logger")


def _post(payload: dict) -> None:
    """Synchronous Supabase insert — runs in a daemon thread."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/query_logs"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        httpx.post(url, json=payload, headers=headers, timeout=5)
    except Exception as exc:
        logger.debug("Query log failed (non-fatal): %s", exc)


def log_query(
    question: str,
    answer_type: str,
    confidence: float,
    latency_ms: int,
    ip: str,
) -> None:
    """Fire-and-forget: log a query to Supabase without blocking the response."""
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
    payload = {
        "question": question[:500],
        "answer_type": answer_type,
        "confidence": round(confidence, 4),
        "latency_ms": latency_ms,
        "ip_hash": ip_hash,
    }
    t = threading.Thread(target=_post, args=(payload,), daemon=True)
    t.start()
