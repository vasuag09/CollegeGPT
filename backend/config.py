"""
NM-GPT – Centralized Configuration

All paths, model settings, and tuneable parameters live here.
Uses python-dotenv to load secrets from a .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── gRPC Configuration ──────────────────────────────────────
# Force gRPC to use the native DNS resolver to avoid c-ares DNS issues
os.environ["GRPC_DNS_RESOLVER"] = "native"

# ── Load .env ────────────────────────────────────────────────
load_dotenv()

# ── Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INDEX_DIR = PROJECT_ROOT / "index"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# PDF documents directory — place all PDFs here before running ingestion
DOCS_DIR = PROJECT_ROOT / "pdfs"

# Generated artefacts
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
FAISS_INDEX_PATH = INDEX_DIR / "faiss_index.bin"
METADATA_PATH = INDEX_DIR / "metadata.json"
PAPERS_REGISTRY_PATH = DATA_DIR / "question_papers.json"

# ── API Keys ─────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── Twilio (WhatsApp) ────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")

# ── Supabase (query logging + admin dashboard) ────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# ── Model Settings ───────────────────────────────────────────
EMBEDDING_MODEL = "models/gemini-embedding-001"
LLM_MODEL = "gemini-2.5-flash"
LLM_TEMPERATURE = 0.2

# ── Chunking ─────────────────────────────────────────────────
CHUNK_SIZE = 1000        # characters per chunk
CHUNK_OVERLAP = 200      # overlap between consecutive chunks

# ── Retrieval ────────────────────────────────────────────────
DEFAULT_TOP_K = 5

# ── Server ───────────────────────────────────────────────────
BACKEND_HOST = "localhost"
BACKEND_PORT = 8000
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

# ── CORS ─────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001"
    ).split(",")
    if o.strip()
]

# ── Input Limits ─────────────────────────────────────────────
MAX_QUESTION_LENGTH = 500

# ── LLM Timeout ──────────────────────────────────────────────
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
