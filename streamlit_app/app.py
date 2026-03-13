"""
CollegeGPT – Streamlit Chat Interface

A chat-style web UI for students to ask questions about the
Student Resource Book (SRB). Communicates with the FastAPI backend.

Usage:
    streamlit run streamlit_app/app.py
"""

import streamlit as st

# MUST be the very first Streamlit command
st.set_page_config(
    page_title="CollegeGPT – Campus Policy Assistant",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

import httpx
import json

# ── Backend URL ──────────────────────────────────────────────
BACKEND_URL = "http://localhost:8000"

# ── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
    }
    .citation-box {
        background-color: #f0f2f6;
        border-left: 4px solid #4CAF50;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.85rem;
    }
    .page-badge {
        display: inline-block;
        background-color: #4CAF50;
        color: white;
        padding: 0.15rem 0.5rem;
        border-radius: 12px;
        font-size: 0.75rem;
        margin: 0.1rem;
    }
    .confidence-bar {
        height: 8px;
        border-radius: 4px;
        margin-top: 0.5rem;
    }
    .stChatMessage {
        padding: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/graduation-cap.png", width=60)
    st.title("CollegeGPT")
    st.caption("Your Campus Policy Assistant 🎓")
    st.divider()

    st.subheader("💡 Example Questions")
    example_questions = [
        "What is the minimum attendance requirement?",
        "What are the rules for exam revaluation?",
        "What happens if I miss an exam due to illness?",
        "What is the grading system used?",
        "What are the rules for internal assessments?",
        "How do I apply for a leave of absence?",
        "What is the anti-ragging policy?",
        "What are the library rules?",
        "What scholarships are available?",
        "What is the code of conduct for students?",
    ]

    for q in example_questions:
        if st.button(q, key=f"example_{q}", use_container_width=True):
            st.session_state["pending_question"] = q

    st.divider()
    st.subheader("⚙️ Settings")
    top_k = st.slider(
        "Number of sources to retrieve",
        min_value=1,
        max_value=10,
        value=5,
        help="More sources = more thorough but slower responses",
    )

    st.divider()
    st.caption("Powered by Google Gemini & FAISS")
    st.caption("Data source: Student Resource Book (SRB) A.Y. 2025-26")


# ── Chat History ─────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# ── Header ───────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🎓 CollegeGPT</h1>
    <p style="color: #666; font-size: 1.1rem;">
        Ask me anything about college policies from the Student Resource Book
    </p>
</div>
""", unsafe_allow_html=True)


# ── Display Chat History ─────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Show citations for assistant messages
        if message["role"] == "assistant" and "citations" in message:
            _render_citations(message) if False else None  # rendered below


def render_response(response_data: dict):
    """Render the assistant response with citations."""
    # Pages badge
    if response_data.get("pages"):
        pages_str = ", ".join(str(p) for p in response_data["pages"])
        st.markdown(f"📄 **Referenced Pages:** {pages_str}")

    # Confidence indicator
    confidence = response_data.get("confidence", 0)
    if confidence > 0:
        color = "#4CAF50" if confidence > 0.6 else "#FFC107" if confidence > 0.3 else "#F44336"
        label = "High" if confidence > 0.6 else "Medium" if confidence > 0.3 else "Low"
        st.progress(confidence, text=f"Confidence: {label} ({confidence:.0%})")

    # Expandable citations
    if response_data.get("citations"):
        with st.expander(f"📚 View Sources ({len(response_data['citations'])} chunks)", expanded=False):
            for i, citation in enumerate(response_data["citations"]):
                page_info = f"Page {citation['page_start']}"
                if citation["page_start"] != citation["page_end"]:
                    page_info = f"Pages {citation['page_start']}–{citation['page_end']}"

                st.markdown(f"""
<div class="citation-box">
    <strong>Source {i + 1}</strong> — <span class="page-badge">{page_info}</span><br/>
    <em>{citation['text']}</em>
</div>
""", unsafe_allow_html=True)


def query_backend(question: str, top_k: int):
    """Send a question to the FastAPI backend."""
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{BACKEND_URL}/query",
                json={"question": question, "top_k": top_k},
            )
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        st.error(
            "⚠️ Cannot connect to the backend server. "
            "Make sure it is running:\n\n"
            "```bash\nuvicorn backend.app:app --reload --port 8000\n```"
        )
        return None
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", str(e))
        st.error(f"⚠️ Backend error: {error_detail}")
        return None
    except Exception as e:
        st.error(f"⚠️ Unexpected error: {str(e)}")
        return None


# ── Handle Input ─────────────────────────────────────────────

# Check for pending question from sidebar
pending = st.session_state.pop("pending_question", None)

# Chat input
user_input = st.chat_input("Ask a question about college policies…")

# Use pending question or user input
question = pending or user_input

if question:
    # Display user message
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Query backend and display response
    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching the Student Resource Book…"):
            result = query_backend(question, top_k)

        if result:
            st.markdown(result["answer"])
            render_response(result)

            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "citations": result.get("citations", []),
                "pages": result.get("pages", []),
                "confidence": result.get("confidence", 0),
            })
        else:
            fallback = "Sorry, I couldn't process your question right now. Please try again."
            st.markdown(fallback)
            st.session_state.messages.append({"role": "assistant", "content": fallback})
