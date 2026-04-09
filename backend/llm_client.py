"""
NM-GPT – LLM Client

Wraps the Google Gen AI model for answer generation.
Uses the google-genai SDK (v1 API endpoint) to avoid v1beta geographic restrictions.

Provides both synchronous (generate) and streaming (generate_stream) interfaces.
"""

import logging
import time
from collections.abc import Generator

from google import genai
from google.genai import types

from backend.config import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_TIMEOUT_SECONDS

logger = logging.getLogger("nmgpt.llm")

_RATE_LIMIT_MESSAGE = (
    "I'm receiving too many requests right now. Please wait a few seconds and try again."
)

# How long to wait before each retry (seconds)
_RETRY_DELAYS = [2, 5]

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return a configured Gen AI client (singleton)."""
    global _client
    if _client is None:
        if not GOOGLE_API_KEY:
            raise ValueError(
                "GOOGLE_API_KEY is not set. "
                "Create a .env file with your key (see .env.example)."
            )
        _client = genai.Client(
            api_key=GOOGLE_API_KEY,
            http_options=types.HttpOptions(api_version="v1"),
        )
    return _client


def _extract_text(response: types.GenerateContentResponse) -> str:
    """Extract plain text from a GenerateContentResponse, skipping thinking parts."""
    parts = []
    for candidate in response.candidates or []:
        for part in candidate.content.parts or []:
            if hasattr(part, "thought") and part.thought:
                continue
            if part.text:
                parts.append(part.text)
    return "".join(parts)


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate" in msg or "resource exhausted" in msg


def generate(prompt: str) -> str:
    """Send a prompt to the LLM and return the text response."""
    logger.info("Invoking LLM (model=%s, timeout=%ds)", LLM_MODEL, LLM_TIMEOUT_SECONDS)
    client = get_client()
    config = types.GenerateContentConfig(
        temperature=LLM_TEMPERATURE,
        http_options=types.HttpOptions(timeout=LLM_TIMEOUT_SECONDS * 1000),
    )
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            logger.warning("Rate limit hit, retrying in %ds (attempt %d)", delay, attempt + 1)
            time.sleep(delay)
        try:
            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
                config=config,
            )
            return _extract_text(response)
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
    client = get_client()
    config = types.GenerateContentConfig(
        temperature=LLM_TEMPERATURE,
        http_options=types.HttpOptions(timeout=LLM_TIMEOUT_SECONDS * 1000),
    )
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            logger.warning("Rate limit hit, retrying stream in %ds (attempt %d)", delay, attempt + 1)
            time.sleep(delay)
        try:
            for chunk in client.models.generate_content_stream(
                model=LLM_MODEL,
                contents=prompt,
                config=config,
            ):
                text = _extract_text(chunk)
                if text:
                    yield text
            return  # success
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit(exc):
                continue
            raise
    logger.error("LLM stream rate limit after retries: %s", last_exc)
    yield _RATE_LIMIT_MESSAGE
