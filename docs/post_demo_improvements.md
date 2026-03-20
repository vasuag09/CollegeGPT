# NM-GPT — Post-Demo Improvement Roadmap

> Generated after dean presentation on 2026-03-20.
> Current state: working prototype with FastAPI backend, FAISS vector search, Gemini 2.5-flash, Next.js chat UI, and multi-document ingestion pipeline.

---

## Priority 1 — Critical for Production

These block real student use. Do these before any campus-wide rollout.

### 1.1 Authentication & User Identity
**Why:** Right now anyone who finds the URL can use the system. No way to know who asked what.

- Add college SSO (Google Workspace / LDAP / OAuth2) login
- Store user ID with each query session
- Restrict access to `@nmims.edu` email domain
- Candidate library: **NextAuth.js** (frontend) + **python-jose** (backend JWT validation)

### 1.2 Query Logging & Analytics
**Why:** Without logs, you cannot improve the system. You have no idea what students are struggling with.

- Log every query: `user_id`, `question`, `retrieved_chunks`, `answer`, `confidence`, `latency`, `timestamp`
- Use **PostgreSQL** (or SQLite for start) via **SQLModel** in the backend
- Build a simple admin dashboard showing:
  - Top 20 questions asked
  - Questions with low confidence (< 0.5) — these reveal gaps in the documents
  - Daily/weekly query volume

### 1.3 Persistent Chat History
**Why:** Sidebar currently shows hardcoded fake conversations. Every page refresh wipes history.

- Backend: store conversations in the same database as logs
- Frontend: replace in-memory state with API calls to `/conversations` endpoints
- Each conversation = `{id, title, messages[], created_at}`

### 1.4 Proper Environment Configuration
**Why:** Backend URL is hardcoded as `http://localhost:8000` in `ChatContainer.tsx`. Will break in any deployed environment.

```ts
// landing/components/chat/ChatContainer.tsx — current
const STREAM_URL = "http://localhost:8000/query/stream";

// Fix: use Next.js env variable
const STREAM_URL = process.env.NEXT_PUBLIC_API_URL + "/query/stream";
```

- Add `.env.local` for Next.js and `.env.production` for backend
- Document all env variables in README

---

## Priority 2 — Robustness & Quality

### 2.1 Add a Test Suite
**Why:** Zero test coverage means any change can silently break things.

**Backend (pytest):**
```
tests/
  test_rag_pipeline.py    # Unit test retrieve, assemble, generate
  test_embeddings.py      # Mock Gemini, test fallback behavior
  test_api.py             # Integration test /query and /health endpoints
```

**Frontend (Vitest + React Testing Library):**
```
landing/__tests__/
  CitationBlock.test.tsx  # Render citations with various confidence values
  ChatContainer.test.tsx  # SSE stream parsing logic
```

### 2.2 Structured Logging
**Why:** Currently the backend prints to stdout with no structure. Impossible to debug in production.

- Replace bare `print()` statements with Python `logging` module
- Log format: `timestamp | level | module | message`
- Log: every query received, retrieval time, generation time, errors with tracebacks

### 2.3 API Rate Limiting
**Why:** No throttle = one student can spam the Gemini API and burn through quota.

- Add **slowapi** middleware to FastAPI
- Limit: 10 requests/minute per IP (or per user once auth exists)
- Return `429 Too Many Requests` with a `Retry-After` header

### 2.4 Input Validation in Frontend
**Why:** No checks before sending to backend. User can send empty strings, 10,000-character queries, etc.

- Minimum query length: 5 characters
- Maximum query length: 500 characters
- Strip leading/trailing whitespace before send

---

## Priority 3 — Better AI Quality

### 3.1 Improve Chunking Strategy
**Why:** Current chunking is purely character-based (1000 chars, 200 overlap). This can split mid-sentence or mid-section.

- Switch to semantic chunking (split at section headers, bullet points, paragraph boundaries)
- Store `section_title` in chunk metadata so citations say "Section 4.2 — Attendance" not just "Page 12"

### 3.2 Hybrid Search (BM25 + Vector)
**Why:** Pure vector search misses exact keyword matches. A student typing "75%" may not retrieve the attendance rule.

- Add **BM25 keyword search** alongside FAISS vector search
- Merge results with **Reciprocal Rank Fusion (RRF)**
- Library: **rank-bm25** (pure Python, no extra infra)

### 3.3 Hallucination Guard
**Why:** Gemini can occasionally extrapolate beyond the retrieved context.

- After generation, verify every `[Page X]` in the answer corresponds to an actually retrieved chunk
- If a page is cited that wasn't retrieved → strip that citation and log a warning
- Add a `grounded: true/false` flag in the API response

### 3.4 Confidence Score Calibration
**Why:** Current confidence is a heuristic (`1 - avg_l2_distance / 2`). Not calibrated to actual correctness.

- Collect 50–100 labeled Q&A pairs from the documents
- Calibrate distance thresholds to actual answer correctness
- Or: use Gemini to self-evaluate answer quality (LLM-as-judge pattern)

### 3.5 Show Source Document in Citations
**Why:** Now that multiple documents are indexed, citations should show which document the answer came from, not just the page number.

- `CitationBlock.tsx` — add `source_doc` display alongside page number
- Backend already includes `source` field in citation objects — frontend just needs to render it

---

## Priority 4 — Feature Expansion

### 4.1 ✅ Multi-Document Support — DONE
The ingestion pipeline now supports multiple documents:
- All PDFs and `.txt` files in `pdfs/` are processed automatically
- Each chunk is tagged with `source_doc` (the filename)
- Currently indexed: SRB, Academic Calendar, TEE Instructions, Code of Conduct, UFM Penalties, Exam Instructions (442 vectors total)

Remaining: show `source_doc` in `CitationBlock.tsx` (see Priority 3.5 above).

### 4.2 Question Paper Links Registry
**Why:** Dean requested previous year question paper access for students.

- Build a `data/question_papers.json` registry: subject, code, semester, year, branch → Google Drive link
- Add a lookup endpoint or integrate into the RAG pipeline as a separate intent
- When student asks for a question paper, return the Drive link directly (no vector search needed)

### 4.3 Admin Panel
**Why:** Updating documents requires a developer running scripts manually.

- Simple web UI with: upload new PDF → re-ingestion, view query logs, test questions
- Lock behind admin authentication

### 4.4 Proactive Suggestions
**Why:** Students don't always know what to ask.

- After every answer, generate 3 related follow-up questions
- Display as clickable chips below the answer

### 4.5 Feedback Collection
**Why:** No way for students to report wrong answers.

- Add 👍 / 👎 buttons on each `MessageBubble`
- Store feedback with the original query + answer
- Review negative feedback weekly to identify retrieval failures

---

## Priority 5 — Deployment & DevOps

### 5.1 Dockerize the Stack
```
Dockerfile.backend    # Python 3.11, uvicorn, copy index/ and data/
Dockerfile.frontend   # Node 20, next build, next start
docker-compose.yml    # backend + frontend + (later) postgres
```

### 5.2 Deploy to Cloud

| Component | Service | Cost |
|-----------|---------|------|
| Backend | Google Cloud Run | Pay-per-request, free tier |
| Frontend | Vercel | Free for Next.js |
| Database | Supabase (PostgreSQL) | Free tier |
| Secrets | Google Secret Manager | Free tier |

### 5.3 CI/CD Pipeline
- GitHub Actions: on push to main → run tests → build Docker image → deploy

### 5.4 Health Monitoring
- **UptimeRobot** (free) — ping `/health` every 5 minutes, email alert on failure
- Set a Gemini API quota alert at 80% usage in Google Cloud Console

---

## Quick Wins (< 1 day each)

| # | Change | File | Impact |
|---|--------|------|--------|
| 1 | Fix hardcoded `localhost:8000` URL | `ChatContainer.tsx` | Enables deployment |
| 2 | Show `source_doc` in citation cards | `CitationBlock.tsx` | Multi-doc citations |
| 3 | Add real sidebar conversation history | `Sidebar.tsx` | Removes fake placeholder data |
| 4 | Add query length validation to ChatInput | `ChatInput.tsx` | Prevents bad API calls |
| 5 | Add `python-logging` to backend | `app.py`, `rag_pipeline.py` | Debuggability |
| 6 | Add `/metrics` data to `/health` endpoint | `backend/app.py` | Monitoring readiness |

---

## Suggested Execution Order

```
Week 1:   Quick wins + fix env config + add logging
Week 2:   Authentication (SSO) + database setup + query logging
Week 3:   Test suite (backend) + rate limiting + hallucination guard
Week 4:   Hybrid search + improved chunking + show source_doc in citations
Month 2:  Question paper registry + admin panel + feedback collection
Month 3:  Dockerize + cloud deployment + CI/CD + monitoring
```

---

## What's Already Good — Don't Over-Engineer

- **RAG architecture** — sound design, no need to change the core flow
- **Multi-document ingestion** — pipeline now handles all PDFs + TXT files automatically
- **Prompt files** — keeping prompts in `.txt` files is the right call
- **Config centralization** — `config.py` is clean, keep adding to it
- **Modular backend** — `embeddings.py`, `llm_client.py`, `rag_pipeline.py` separation is correct
- **SSE streaming** — real-time token streaming is production-grade, keep it
- **FAISS** — fine for current scale; only swap to Pinecone/Weaviate when you have 50+ documents
