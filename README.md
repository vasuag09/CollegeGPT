# NM-GPT — AI Assistant for NMIMS Students

NM-GPT is a Retrieval-Augmented Generation (RAG) system that lets students ask natural language questions about NMIMS institutional documents and receive accurate, cited answers in real time.

Built with Google Gemini 2.5-flash, FAISS, FastAPI, and Next.js.

**Demonstrated to NMIMS administration on 20 March 2026.**

---

## Features

- Natural language Q&A across 6 official NMIMS documents
- Real-time streaming responses via SSE
- Page citations with every answer
- Expandable source excerpts showing the exact text used
- Confidence score per response
- Conversational memory — AI understands follow-up questions contextually using query rewriting
- Follow-up suggestion pills after each AI response (keyword-matched)
- Persistent chat history via localStorage — survives page refresh
- Multi-conversation sidebar with relative timestamps
- Previous year question paper links (Google Drive) via in-chat search
- Admin dashboard at `/admin` with query stats, hourly chart, top questions
- Query logging to Supabase (fire-and-forget, no latency impact)
- Modular architecture — new documents can be added in minutes

---

## Knowledge Base

The system currently indexes:

| Document | Pages |
|---|---|
| Student Resource Book (SRB) A.Y. 2025-26 | 112 |
| Academic Calendar MPSTME 2025-26 | — |
| TEE Exam Instructions | 2 |
| Student Code of Conduct for Examinations | 2 |
| UFM Offence Penalties A.Y. 2025-26 | 3 |
| University Examination Student Instructions | 2 |

**Total: 442 FAISS vectors (3072-dim)**

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- A Google Gemini API key — [get one free at Google AI Studio](https://aistudio.google.com/apikey)

### 1. Install dependencies

```bash
pip install -r requirements.txt
cd landing && npm install && cd ..
```

### 2. Configure your API key

```bash
cp .env.example .env
# Add your GOOGLE_API_KEY to .env
```

### 3. Run the ingestion pipeline

Only needed once, or when adding new documents to `pdfs/`.

```bash
python scripts/extract_pdf.py
python scripts/chunk_documents.py
python scripts/build_index.py
```

`build_index.py` handles Gemini API rate limits automatically with batching and resume-on-interrupt.

### 4. Start the backend

```bash
python -m uvicorn backend.app:app --host localhost --port 8000
```

Verify: [http://localhost:8000/health](http://localhost:8000/health)

### 5. Start the frontend

```bash
cd landing && npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## Adding New Documents

1. Place the PDF (or `.txt` for scanned PDFs) in the `pdfs/` directory
2. Re-run the ingestion pipeline (steps 3 above)
3. Restart the backend

The pipeline automatically detects all files in `pdfs/` and tags each chunk with its source document.

---

## Project Structure

```
backend/
  app.py                FastAPI server — /health, /query, /query/stream, /admin/stats
  rag_pipeline.py       Core RAG logic
  embeddings.py         Gemini embedding wrapper
  llm_client.py         Gemini LLM client with SSE streaming + rate-limit retries
  query_logger.py       Fire-and-forget Supabase query logger
  config.py             Centralized configuration
  prompts/
    system_prompt.txt
    retrieval_prompt.txt

scripts/
  extract_pdf.py        pdfs/ (PDFs + TXT) -> data/pages.json
  chunk_documents.py    pages.json -> data/chunks.jsonl
  build_index.py        chunks.jsonl -> FAISS index + metadata
  build_papers_registry.py  Builds data/question_papers.json from Google Drive

landing/                Next.js frontend (primary UI)
  app/
    admin/
      layout.tsx        Password-gated admin auth wrapper
      page.tsx          Admin dashboard — stats, charts, top questions
  components/
    Sidebar.tsx         Recent Chats + Knowledge Base
    chat/
      ChatLayout.tsx    localStorage persistence + conversation management
      ChatContainer.tsx SSE stream reader, follow-up suggestion generation
      ChatInput.tsx
      MessageBubble.tsx
      CitationBlock.tsx
      EmptyState.tsx

streamlit_app/
  app.py                Streamlit backup UI (no streaming)

pdfs/                   Source documents for ingestion
data/                   Generated data (gitignored: chunks.jsonl)
index/                  FAISS index + metadata (gitignored)
docs/
  architecture.md
  project_explanation.md
  post_demo_improvements.md
```

---

## API Reference

### POST /query

Synchronous query — waits for the full answer.

```json
{
    "question": "What is the minimum attendance requirement?",
    "top_k": 5
}
```

Response:

```json
{
    "answer": "The minimum attendance requirement is 75%. [Page 12]",
    "citations": [
        {
            "text": "Students must maintain at least 75% attendance...",
            "page_start": 12,
            "page_end": 12,
            "chunk_id": "chunk_0042"
        }
    ],
    "pages": [12],
    "confidence": 0.85
}
```

### POST /query/stream

Streaming query — returns Server-Sent Events. Used by the Next.js frontend.

Event types: `token`, `citations`, `done`, `error`

### GET /health

Returns `{"status": "healthy", "service": "NM-GPT"}`

### GET /admin/stats

Returns query statistics for the last 7 days. Requires `X-Admin-Password` header.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 2.5-flash |
| Embeddings | Gemini embedding-001 (3072-dim) |
| Vector DB | FAISS (IndexFlatL2) |
| Backend | FastAPI + Uvicorn + slowapi (rate limiting) |
| Primary Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Framer Motion |
| Backup Frontend | Streamlit |
| PDF Parsing | PyMuPDF |
| Text Splitting | LangChain RecursiveCharacterTextSplitter |

---

## Architecture

```
pdfs/ (PDFs + TXTs)
    -> extract_pdf.py    (text + source_doc per page)
    -> chunk_documents.py (1000-char chunks, 200 overlap)
    -> build_index.py    (Gemini embeddings -> FAISS)

Student question
    -> embed query (Gemini, 3072-dim)
    -> FAISS L2 search (top-5 chunks)
    -> assemble context with [Page X] annotations
    -> Gemini 2.5-flash generates answer (streamed)
    -> extract citations + confidence score
    -> return to student
```

See [docs/architecture.md](docs/architecture.md) for a detailed breakdown.

---

## Known Limitations

- No authentication — the API is open
- Confidence score is a heuristic based on L2 distance, not calibrated
- Chat history is local (localStorage) — not synced across devices or browsers

### Configuration

The frontend reads `NEXT_PUBLIC_API_URL` from `landing/.env.local`. Set this to point to your deployed backend before hosting.

The backend reads `ALLOWED_ORIGINS` (comma-separated) and `LLM_TIMEOUT_SECONDS` from `.env`. See `.env.example`.

See [docs/post_demo_improvements.md](docs/post_demo_improvements.md) for the full prioritized roadmap.

---

## Built By

Vasu Agrawal and Vanisha Sharma — MPSTME, NMIMS Mumbai

For educational and institutional use.
