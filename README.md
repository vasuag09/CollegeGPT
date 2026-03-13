# 🎓 CollegeGPT — Campus Policy AI Assistant

CollegeGPT is a **Retrieval-Augmented Generation (RAG)** system that lets students ask natural language questions about the Student Resource Book (SRB) and receive answers with page citations.

Built with **Google Gemini**, **FAISS**, **FastAPI**, and **Streamlit**.

---

## ✨ Features

- 💬 **Natural language Q&A** about college policies
- 📄 **Page citations** in every answer
- 📚 **Source text preview** — see the exact text used to generate the answer
- 📊 **Confidence score** for each response
- ⚡ **Fast local execution** — runs entirely on your machine
- 🧩 **Modular architecture** — ready for future expansion

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- A [Google Gemini API key](https://aistudio.google.com/apikey)

### 1. Install Dependencies

```bash
cd CollegeGPT
pip install -r requirements.txt
```

### 2. Set Up Your API Key

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 3. Run the Ingestion Pipeline

```bash
# Step 1: Extract text from the SRB PDF
python scripts/extract_pdf.py

# Step 2: Split into chunks
python scripts/chunk_documents.py

# Step 3: Generate embeddings and build the vector index
python scripts/build_index.py
```

### 4. Start the Backend

```bash
uvicorn backend.app:app --reload --port 8000
```

Verify it's running: open [http://localhost:8000/health](http://localhost:8000/health)

### 5. Start the Chat Interface

```bash
streamlit run streamlit_app/app.py
```

Open the Streamlit URL (usually [http://localhost:8501](http://localhost:8501)) and start asking questions!

---

## 📂 Project Structure

```
CollegeGPT/
├── backend/
│   ├── app.py              # FastAPI backend
│   ├── config.py           # Centralized configuration
│   ├── embeddings.py       # Embedding model wrapper
│   ├── llm_client.py       # Gemini LLM client
│   ├── rag_pipeline.py     # RAG pipeline (retrieve → generate → cite)
│   └── prompts/
│       ├── system_prompt.txt
│       └── retrieval_prompt.txt
├── scripts/
│   ├── extract_pdf.py      # PDF text extraction
│   ├── chunk_documents.py  # Document chunking
│   └── build_index.py      # FAISS index builder
├── streamlit_app/
│   └── app.py              # Streamlit chat interface
├── data/                   # Generated data (chunks, pages)
├── index/                  # Generated FAISS index
├── docs/
│   ├── architecture.md     # Architecture overview
│   └── demo_script.md      # Demo flow & questions
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔌 API Reference

### `POST /query`

**Request:**
```json
{
    "question": "What is the minimum attendance requirement?",
    "top_k": 5
}
```

**Response:**
```json
{
    "answer": "The minimum attendance requirement is 75%... [Page 12]",
    "citations": [
        {
            "text": "Students must maintain...",
            "page_start": 12,
            "page_end": 12,
            "chunk_id": "chunk_0042"
        }
    ],
    "pages": [12],
    "confidence": 0.85
}
```

### `GET /health`

Returns `{"status": "healthy", "service": "CollegeGPT"}`

---

## 🏗️ Architecture

See [docs/architecture.md](docs/architecture.md) for a detailed architecture overview with diagrams.

**TL;DR:**

```
SRB PDF → Extract → Chunk → Embed → FAISS Index
                                        ↓
Student Question → Embed → Search FAISS → Assemble Context → Gemini → Cited Answer
```

---

## 🎯 Demo

See [docs/demo_script.md](docs/demo_script.md) for a 2-minute demo flow with 10 example questions.

---

## 🔮 Future Expansion

The modular architecture supports:

- 📁 Multi-document knowledge bases
- 🏢 Department-specific data
- 🌐 College website ingestion
- 💼 Placement & internship info
- 📅 Timetable systems
- 👨‍🏫 Faculty directories
- 📊 Analytics dashboards
- 🔐 SSO authentication

---

## 📝 License

This project is for educational and institutional use.
