"""
NM-GPT – LLM Client

Wraps the Google Generative AI chat model for answer generation.
Uses LangChain's ChatGoogleGenerativeAI for consistency with the
rest of the pipeline.

Provides both synchronous (generate) and streaming (generate_stream)
interfaces.
"""

import logging
import time
from collections.abc import Generator

from backend.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_TIMEOUT_SECONDS

from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger("nmgpt.llm")

_RATE_LIMIT_MESSAGE = (
    "I'm receiving too many requests right now. Please wait a few seconds and try again."
)

# How long to wait before each retry (seconds)
_RETRY_DELAYS = [2, 5]


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
        transport="rest",
        timeout=LLM_TIMEOUT_SECONDS,
    )


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate" in msg or "resource exhausted" in msg


def generate(prompt: str) -> str:
    """Send a prompt to the LLM and return the text response."""
    logger.info("Invoking LLM (model=%s, timeout=%ds)", LLM_MODEL, LLM_TIMEOUT_SECONDS)
    llm = get_llm()
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            logger.warning("Rate limit hit, retrying in %ds (attempt %d)", delay, attempt + 1)
            time.sleep(delay)
        try:
            response = llm.invoke(prompt)
            content = response.content
            if isinstance(content, list):
                return "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                    if not (isinstance(part, dict) and part.get("type") == "thinking")
                )
            return str(content)
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit(exc):
                continue
            raise
    logger.error("LLM rate limit after retries: %s", last_exc)
    return _RATE_LIMIT_MESSAGE


def generate_stream(prompt: str) -> Generator[str, None, None]:
    """Stream tokens from the LLM, yielding each chunk as it arrives."""
    logger.info("Streaming LLM (model=%s, timeout=%ds)", LLM_MODEL, LLM_TIMEOUT_SECONDS)
    llm = get_llm()
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            logger.warning("Rate limit hit, retrying stream in %ds (attempt %d)", delay, attempt + 1)
            time.sleep(delay)
        try:
            for chunk in llm.stream(prompt):
                content = chunk.content
                if not content:
                    continue
                if isinstance(content, list):
                    text = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                        if not (isinstance(part, dict) and part.get("type") == "thinking")
                    )
                    if text:
                        yield text
                else:
                    yield str(content)
            return  # success
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit(exc):
                continue
            raise
    logger.error("LLM stream rate limit after retries: %s", last_exc)
    yield _RATE_LIMIT_MESSAGE
