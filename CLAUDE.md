# Claude Development Guide — NM-GPT

## Project Overview

NM-GPT is an AI assistant that answers student questions using NMIMS institutional documents — the Student Resource Book, Academic Calendar, examination rules, and related policies for A.Y. 2025-26.

The system uses a Retrieval Augmented Generation (RAG) architecture powered by the Gemini API.

The prototype was demonstrated to college administration on 2026-03-20. The dean requested expanded document coverage, which has been added. Future versions may evolve into a campus-wide AI platform.

Built by: Vasu Agrawal and Vanisha Sharma.

---

# Your Role

You are assisting as a senior AI engineer helping build and improve NM-GPT.

Focus on:

• clean architecture
• modular design
• working code
• clear explanations
• practical implementation

Avoid unnecessary complexity.

---

# Current Implementation Status

The prototype is complete and demo-ready. The following components are built and working:

**Backend**
- FastAPI REST server on port 8000
- `/health` — health check
- `/query` — synchronous RAG query
- `/query/stream` — SSE streaming RAG query (primary endpoint used by frontend)
- `/admin/stats` — query statistics for last 7 days (requires `X-Admin-Password` header)
- `/webhook/whatsapp` — Twilio webhook; accepts form POST (`From`, `Body`), runs RAG with per-phone session history, returns TwiML XML
- `backend/app.py`, `backend/rag_pipeline.py`, `backend/embeddings.py`, `backend/llm_client.py`, `backend/config.py`
- `backend/query_logger.py` — fire-and-forget Supabase logger (daemon thread, no latency impact)
- Prompts stored as plain text files in `backend/prompts/`
- Greeting detection — common greetings bypass the LLM and return an instant response
- Rate limit retry in `llm_client.py` — retries up to 2× on 429/quota; handles gemini-2.5-flash thinking-model list content

**Tests**
- Backend: 145 pytest tests covering config, embeddings, llm_client, rag_pipeline, API endpoints, rate limiting, WhatsApp webhook, Drive uploader, sync orchestrator
- Frontend: 81 Vitest tests covering ChatInput, CitationBlock, MessageBubble, EmptyState, ChatContainer
- Run backend: `pytest` from project root
- Run frontend: `npm run test:run` from `landing/`

**Ingestion Pipeline** (multi-document, run after adding new files to `pdfs/`)
- `scripts/extract_pdf.py` — all PDFs + TXT files in `pdfs/` → `data/pages.json` (each page tagged with `source_doc`)
- `scripts/chunk_documents.py` — pages → `data/chunks.jsonl` (442 chunks)
- `scripts/build_index.py` — chunks → `index/faiss_index.bin` + `index/metadata.json`

**PYQ Scraper Pipeline** (run separately to sync question papers to Google Drive)
- `scripts/pyq_scraper.py` — Playwright scraper that logs into SVKM portal and downloads PYQ PDFs to `data/pyqs/`
- `scripts/drive_uploader.py` — Google Drive API v3 uploader; creates folder tree, uploads idempotently, deletes local copy on success; upload registry at `data/pyqs_uploaded.txt`
- `scripts/sync_pyqs.py` — orchestrator: authenticate Drive → scrape → upload file-by-file → report counts; supports `--branch` flag for parallelism
- `scripts/inspect_portal.py` — one-off Playwright script for SVKM portal CSS selector discovery; requires `SVKM_USERNAME`/`SVKM_PASSWORD` in `.env`
- Requires: `SVKM_USERNAME`, `SVKM_PASSWORD`, `GOOGLE_DRIVE_FOLDER_NAME` in `.env`; `credentials.json` (Google OAuth) at project root

**Frontends**
- Next.js 16 + React 19 + TypeScript + Tailwind CSS + Framer Motion — primary UI at `landing/`
- Admin dashboard at `landing/app/admin/` — sessionStorage password gate, query stats, hourly SVG chart
- Streamlit — backup UI at `streamlit_app/app.py`

**Chat Features**
- Conversational memory — AI understands follow-up questions via query rewriting (`_rewrite_query` in `rag_pipeline.py`)
- PYQ acronym mapping — `_ACRONYMS` dict expands subject codes (e.g. "DBMS" → `["DATABASE", "MANAGEMENT"]`) before token scoring in paper search
- Chat history persisted in `localStorage` — survives page refresh, max 20 conversations
- Multi-conversation sidebar with relative timestamps ("Just now", "5m ago", etc.)
- Follow-up suggestion pills after each AI response (keyword-matched, 8 topic categories)
- Previous year question papers accessible via in-chat lookup (`data/question_papers.json`)
- WhatsApp channel — students can chat with NM-GPT on WhatsApp via Twilio; per-phone session history kept in memory (last 6 messages)

**Indexed Documents** (in `pdfs/`)
- `Final SRB A.Y. 2025-26 .................................pdf` — 112 pages
- `Academic Calendar MPSTME 2025-26.txt` — academic calendar (text file, scanned PDF was unreadable)
- `INSTRUCTIONS TO STUDENTS FOR TEE EXAM (003).pdf` — 2 pages
- `Student Code of Conduct for Examinations.pdf` — 2 pages
- `UFM_offence penalty_AY_2025-26.pdf` — 3 pages
- `University Examination Student Instructions.pdf` — 2 pages
- Total: 442 FAISS vectors (3072-dim, L2 search)

---

# Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Gemini 2.5-flash |
| Embeddings | Gemini embedding-001 (3072-dim) |
| Vector DB | FAISS (IndexFlatL2) |
| Backend | FastAPI + Uvicorn |
| Frontend (primary) | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Framer Motion |
| Frontend (alt) | Streamlit 1.41.1 |
| PDF Parsing | PyMuPDF (fitz) |
| Text Splitting | LangChain RecursiveCharacterTextSplitter |
| Config | python-dotenv, centralized in `backend/config.py` |
| Backend Testing | pytest 8.3.5 + pytest-asyncio |
| Frontend Testing | Vitest 3 + React Testing Library + jsdom |

---

# Key Configuration Values

Defined in `backend/config.py`:

- DOCS_DIR: `pdfs/` — place all source documents here
- CHUNK_SIZE: 1000 characters
- CHUNK_OVERLAP: 200 characters
- DEFAULT_TOP_K: 5
- LLM_MODEL: "gemini-2.5-flash"
- EMBEDDING_MODEL: "models/gemini-embedding-001"
- LLM_TEMPERATURE: 0.2
- BACKEND_HOST: "localhost"
- BACKEND_PORT: 8000
- PYQ_DIR: `data/pyqs/` — local download directory for scraped PYQs
- SVKM_PORTAL_URL: SVKM portal login URL
- GOOGLE_DRIVE_FOLDER_NAME: root Drive folder for uploaded PYQs (from env)
- GOOGLE_CREDENTIALS_PATH: `credentials.json` at project root (Google OAuth)
- GOOGLE_TOKEN_PATH: `token.json` at project root (refreshed automatically)

Environment variables required in `.env`:
- `GOOGLE_API_KEY` — Gemini API key
- `SVKM_USERNAME`, `SVKM_PASSWORD` — SVKM portal credentials (PYQ scraper)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` — Twilio WhatsApp credentials
- `GOOGLE_DRIVE_FOLDER_NAME` — Drive root folder name (default: "NMIMS PYQs")
- `SUPABASE_URL`, `SUPABASE_KEY`, `ADMIN_PASSWORD` — Supabase query logging + admin dashboard

---

# Core Architecture

NM-GPT consists of four layers.

## 1 Document Ingestion

Responsibilities:

Load all PDFs and TXT files from `pdfs/`
Extract text page-by-page, tagging each page with `source_doc` (filename)
Chunk text (1000 chars, 200 overlap)
Generate embeddings via Gemini

To add a new document: place it in `pdfs/` and re-run the three ingestion scripts.

For scanned/image-based PDFs that PyMuPDF cannot read: save the text content as a `.txt` file in `pdfs/` instead.

Output:

data/pages.json
data/chunks.jsonl
index/faiss_index.bin
index/metadata.json

---

## 2 Vector Database

Stores embeddings of document chunks using FAISS (IndexFlatL2).

Each stored record in metadata.json contains:

chunk_id
text
page_start
page_end
source   ← the source document filename (e.g. "Final SRB A.Y. 2025-26 ...")

---

## 3 RAG Pipeline

Processing steps:

1 Query received
2 Query embedded via Gemini (3072-dim)
3 FAISS L2 search retrieves top-K chunks
4 Context assembled with [Page X] annotations
5 Prompt built from system_prompt.txt + retrieval_prompt.txt + context + question
6 Gemini 2.5-flash generates answer
7 Citations and confidence extracted

The model must only answer using retrieved context.

Confidence = 1 - (avg_l2_distance / 2). Heuristic, not calibrated.

---

## 4 Application Layer

**Backend (FastAPI):** handles RAG pipeline, API endpoints, SSE streaming, WhatsApp webhook

**Frontend (Next.js primary):**
- `landing/components/chat/ChatLayout.tsx` — localStorage persistence, conversation management, active conv state
- `landing/components/chat/ChatContainer.tsx` — core logic, SSE stream reader, follow-up suggestion generation
- `landing/components/chat/MessageBubble.tsx` — renders user/AI messages with markdown + follow-up pills
- `landing/components/chat/CitationBlock.tsx` — confidence bar + expandable evidence cards
- `landing/components/chat/ChatInput.tsx` — auto-resizing textarea, Enter to send
- `landing/components/chat/EmptyState.tsx` — suggestions UI on first load
- `landing/components/Sidebar.tsx` — Recent Chats (real conversations) + Knowledge Base section
- `landing/app/admin/layout.tsx` — sessionStorage password gate for admin area
- `landing/app/admin/page.tsx` — admin dashboard: stat cards, hourly SVG chart, top questions, answer types

**Frontend config:** Backend URL is read from `NEXT_PUBLIC_API_URL` in `landing/.env.local`. Change this env var before deploying.

---

# Development Guidelines

When generating code:

Prefer Python for backend.

Keep modules small and readable.

Separate responsibilities:

ingestion
embeddings
retrieval
generation
UI

Avoid mixing logic across files.

For frontend, use TypeScript. Follow existing component patterns in `landing/components/`.

---

# Prompting Rules for LLM

The model must follow these rules:

Only answer using retrieved context.

If information is not present in the context, respond with:

"I could not find this information in the Student Resource Book."

Always include page citations.

Answers should be concise.

Prompts are in `backend/prompts/system_prompt.txt` and `backend/prompts/retrieval_prompt.txt` — edit these files to change LLM behavior without touching code.

---

# File Map

```
backend/
  app.py               FastAPI server, endpoints, CORS, /admin/stats
  rag_pipeline.py      Core RAG orchestration
  embeddings.py        Gemini embedding wrapper
  llm_client.py        Gemini LLM client with streaming + rate-limit retries
  query_logger.py      Fire-and-forget Supabase query logger
  config.py            All settings and paths (single source of truth)
  prompts/
    system_prompt.txt
    retrieval_prompt.txt

scripts/
  extract_pdf.py             pdfs/ (PDFs + TXT) → pages.json
  chunk_documents.py         pages.json → chunks.jsonl
  build_index.py             chunks.jsonl → faiss_index.bin + metadata.json
  build_papers_registry.py   builds data/question_papers.json from Google Drive
  pyq_scraper.py             Playwright scraper — SVKM portal → data/pyqs/
  drive_uploader.py          Google Drive API v3 uploader (idempotent, OAuth2)
  sync_pyqs.py               Orchestrator: scrape → upload → delete local copies
  inspect_portal.py          One-off portal inspection script for CSS selector discovery
  verify_api.py              API smoke test

streamlit_app/
  app.py               Streamlit chat UI (backup frontend)

landing/               Next.js frontend (primary)
  app/
    layout.tsx
    page.tsx
    admin/
      layout.tsx       Password gate (sessionStorage)
      page.tsx         Admin dashboard — stats, hourly chart, top questions
  components/
    Sidebar.tsx        Recent Chats + Knowledge Base (collapsible)
    chat/
      ChatLayout.tsx   localStorage conversation management
      ChatContainer.tsx SSE reader + follow-up suggestion generation
      ChatInput.tsx
      MessageBubble.tsx Follow-up suggestion pills
      EmptyState.tsx
      CitationBlock.tsx

pdfs/                  Source documents for ingestion
  Final SRB A.Y. 2025-26 .................................pdf
  Academic Calendar MPSTME 2025-26.txt
  INSTRUCTIONS TO STUDENTS FOR TEE EXAM (003).pdf
  Student Code of Conduct for Examinations.pdf
  UFM_offence penalty_AY_2025-26.pdf
  University Examination Student Instructions.pdf

data/
  pages.json           Extracted text per page (with source_doc)
  chunks.jsonl         442 processed chunks

index/
  faiss_index.bin      FAISS binary index
  metadata.json        Chunk metadata

tests/                 Backend test suite (pytest, 145 tests)
  conftest.py          Shared fixtures (client, mock_pipeline, rate limit management)
  test_config.py       Config values and env override tests
  test_embeddings.py   Embedding model and API wrapper tests
  test_llm_client.py   LLM client and streaming tests
  test_rag_pipeline.py RAG pipeline unit tests (prompt injection, citations, retrieval)
  test_api.py          FastAPI endpoint tests (health, query, stream, CORS, rate limiting)
  test_whatsapp.py     WhatsApp webhook tests (session history, TwiML response, error cases)
  test_drive_uploader.py  Drive uploader unit tests (auth, folder creation, upload, registry)
  test_sync_pyqs.py    Sync orchestrator tests (branch filtering, scraper/uploader integration)

landing/__tests__/     Frontend test suite (Vitest)
  setup.ts             Test environment setup
  ChatInput.test.tsx
  CitationBlock.test.tsx
  MessageBubble.test.tsx
  EmptyState.test.tsx
  ChatContainer.test.tsx

pytest.ini             Backend test configuration
landing/vitest.config.ts  Frontend test configuration

docs/
  architecture.md
  project_explanation.md
  post_demo_improvements.md   Prioritized roadmap for post-demo work
  whatsapp.md                 WhatsApp integration setup guide (Twilio sandbox + production)
```

---

# Known Gaps (post-demo backlog)

These are known and intentional omissions for the prototype. Do not add complexity unless explicitly asked.

**Critical before production:**
- No authentication — anyone can query the API
- Chat history is localStorage only — not synced across devices or browsers

**Quality:**
- Confidence score is a heuristic, not calibrated

**AI quality:**
- Character-based chunking, not semantic
- Pure vector search — no BM25 hybrid
- No hallucination guard on cited pages
- Streamlit UI has no SSE streaming (blocks on response)

**Already addressed (no longer gaps):**
- Backend URL now read from `NEXT_PUBLIC_API_URL` env var
- Structured logging added to all backend modules
- Rate limiting on `/query` and `/query/stream` (10 req/min via slowapi)
- Input validation: 1–500 char limit, enforced on both frontend and backend
- `/health` now checks index files and API key, returns 503 if not ready
- 60s timeout on LLM calls (configurable via `LLM_TIMEOUT_SECONDS`)
- Frontend fetch timeout via AbortController (60s)
- Citation source field populated from chunk metadata
- Prompt injection fix: `_build_prompt` uses `str.partition()` — prevents cross-substitution between context and question
- Citation fallback removed — pages list is empty if LLM doesn't cite
- Greeting detection in RAG pipeline — common greetings (hi, hello, hey, etc.) return an instant friendly response without hitting the LLM or FAISS
- Full test suite added: 129 backend tests (pytest) + 81 frontend tests (Vitest)
- Chat history persisted in localStorage — max 20 conversations, survives refresh
- Multi-conversation sidebar with real data + relative timestamps
- Follow-up suggestion pills added to MessageBubble (keyword-matched, post-response)
- Query logging to Supabase via `query_logger.py` (fire-and-forget daemon thread)
- Admin dashboard at `/admin` — password gate, stat cards, hourly chart, top questions, auto-refresh 30s
- PYQ registry (`data/question_papers.json`) and in-chat question paper search
- Rate limit retry + gemini-2.5-flash thinking-model list content handling in `llm_client.py`
- WhatsApp chatbot via Twilio — `/webhook/whatsapp` endpoint with per-phone in-memory session history
- PYQ scraper + Drive uploader — `scripts/pyq_scraper.py`, `drive_uploader.py`, `sync_pyqs.py`; downloads from SVKM portal and syncs to Google Drive with idempotent upload registry
- Conversational memory + acronym mapping in PYQ search — `_rewrite_query()` and `_ACRONYMS` in `rag_pipeline.py`

Full prioritized roadmap: `docs/post_demo_improvements.md`

---

# Code Assistance Expectations

When asked for help, you should:

Provide working code snippets.

Explain design decisions briefly.

Suggest improvements if architecture can be simplified.

Avoid overly abstract designs.

Check `backend/config.py` before hardcoding any paths, model names, or settings.

---

# Future Expansion

The system may later expand to support:

question paper links registry — built (`data/question_papers.json` → Google Drive links)
PYQ scraper + Drive sync — built (`scripts/pyq_scraper.py`, `drive_uploader.py`, `sync_pyqs.py`)
WhatsApp chatbot — built (`/webhook/whatsapp` via Twilio)
more institutional documents in pdfs/
department knowledge bases
college website ingestion
placement information
timetable systems
faculty directory
student service workflows
analytics dashboards
SSO authentication

Adding new documents is straightforward: drop a PDF or TXT into `pdfs/` and re-run the three ingestion scripts.

---

# Performance Priorities

Now that the prototype is demonstrated, priorities shift:

1. Correctness and reliability
2. Authentication and logging
3. Test coverage
4. Production deployment

Do not optimize prematurely. FAISS search on 442 vectors is <1ms — not a bottleneck. Gemini API latency dominates.

---

# Demo Goal (achieved 2026-03-20)

The system successfully answers questions such as:

"What is the minimum attendance requirement?"
"What are the rules for exam revaluation?"
"What happens if I miss an exam due to illness?"
"When are the Term End Exams for Semester I?"
"What are the consequences of UFM offences?"

Answers include page citations from the relevant source document.

---

# Final Objective

Deliver a working AI assistant that demonstrates how institutional knowledge can be transformed into a conversational interface for students.

Focus on practicality and clarity.
