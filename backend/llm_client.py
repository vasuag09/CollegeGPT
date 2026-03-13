"""
CollegeGPT – LLM Client

Wraps the Google Generative AI chat model for answer generation.
Uses LangChain's ChatGoogleGenerativeAI for consistency with the
rest of the pipeline.

Provides both synchronous (generate) and streaming (generate_stream)
interfaces.
"""

from collections.abc import Generator

from backend.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE

from langchain_google_genai import ChatGoogleGenerativeAI


def get_llm() -> ChatGoogleGenerativeAI:
    """Return a configured LLM instance."""
    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY is not set. "
            "Create a .env file with your key (see .env.example)."
        )
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=LLM_TEMPERATURE,
    )


def generate(prompt: str) -> str:
    """Send a prompt to the LLM and return the text response."""
    llm = get_llm()
    response = llm.invoke(prompt)
    return str(response.content)


def generate_stream(prompt: str) -> Generator[str, None, None]:
    """Stream tokens from the LLM, yielding each chunk as it arrives."""
    llm = get_llm()
    for chunk in llm.stream(prompt):
        if chunk.content:
            yield str(chunk.content)
