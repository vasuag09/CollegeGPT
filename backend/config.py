"""
NM-GPT – Centralized Configuration

All paths, model settings, and tuneable parameters live here.
Uses python-dotenv to load secrets from a .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────
load_dotenv()

# ── Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INDEX_DIR = PROJECT_ROOT / "index"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Source PDF
SRB_PDF_PATH = PROJECT_ROOT / "Final SRB A.Y. 2025-26 .................................pdf"

# Generated artefacts
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
FAISS_INDEX_PATH = INDEX_DIR / "faiss_index.bin"
METADATA_PATH = INDEX_DIR / "metadata.json"

# ── API Keys ─────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

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
