# Claude Development Guide — NM-GPT

## Project Overview

NM-GPT is a prototype AI assistant that answers student questions using a Student Resource Book (SRB) containing approximately 100 pages of official policies.

The system uses a Retrieval Augmented Generation (RAG) architecture powered by the Gemini API.

The prototype must run locally and demonstrate the concept to college administration.

Future versions may evolve into a campus-wide AI platform.

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

# Core Architecture

NM-GPT consists of four main layers.

## 1 Document Ingestion

Responsibilities:

Load SRB PDF
Extract text
Preserve page numbers
Chunk text into segments
Generate embeddings

Output:

chunks.jsonl
vector index

---

## 2 Vector Database

Stores embeddings of document chunks.

Preferred option:

FAISS

Alternative:

Chroma

Each stored record contains:

chunk_id
text
page_start
page_end
source

---

## 3 RAG Pipeline

Processing steps:

1 Query received
2 Query embedding generated
3 Vector search retrieves top chunks
4 Context assembled
5 Prompt built for Gemini
6 Gemini generates answer
7 Citations extracted

The model must only answer using retrieved context.

---

## 4 Application Layer

Two components:

FastAPI backend
Streamlit chat interface

Backend handles:

RAG pipeline
API endpoints
LLM interaction

Streamlit handles:

chat UI
displaying answers
showing citations

---

# Development Guidelines

When generating code:

Prefer Python.

Keep modules small and readable.

Separate responsibilities:

ingestion
embeddings
retrieval
generation
UI

Avoid mixing logic across files.

---

# Prompting Rules for LLM

The model must follow these rules:

Only answer using retrieved context.

If information is not present in the context, respond with:

"I could not find this information in the Student Resource Book."

Always include page citations.

Answers should be concise.

---

# Expected Files

backend/app.py
backend/rag_pipeline.py
backend/embeddings.py
backend/llm_client.py

scripts/extract_pdf.py
scripts/build_index.py

streamlit_app/app.py

data/chunks.jsonl
index/faiss_index.bin

docs/architecture.md
docs/demo_script.md

---

# Code Assistance Expectations

When asked for help, you should:

Provide working code snippets.

Explain design decisions briefly.

Suggest improvements if architecture can be simplified.

Avoid overly abstract designs.

---

# Future Expansion

The system may later expand to support:

multiple documents
department knowledge bases
college website ingestion
placement information
timetable systems
faculty directory
student service workflows
analytics dashboards
SSO authentication

Design code so these extensions can be added without major refactoring.

---

# Performance Priorities

For the prototype prioritize:

speed of development
clarity
reliability
demo stability

Do not optimize prematurely.

---

# Demo Goal

The system must successfully answer questions such as:

"What is the minimum attendance requirement?"

"What are the rules for exam revaluation?"

"What happens if I miss an exam due to illness?"

Answers must include page citations from the SRB.

---

# Final Objective

Deliver a working AI assistant that demonstrates how institutional knowledge can be transformed into a conversational interface for students.

Focus on practicality and clarity.
