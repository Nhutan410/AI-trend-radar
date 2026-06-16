"""
core/llm_provider.py
--------------------
OpenAI-backed LLM provider.

Load OPENAI_API_KEY from .env file at project root (via python-dotenv).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load .env at project root
# ---------------------------------------------------------------------------
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_PATH, override=True)
    except ImportError:
        logger.warning("python-dotenv chưa cài — chạy: pip install python-dotenv")


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = 90
LLM_TIMEOUT = 120


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_openai_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return key if key and not key.startswith("sk-your") else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_active_provider() -> str:
    """
    Determine which LLM backend is active.

    Returns
    -------
    'openai' | 'none'
    """
    if _get_openai_key():
        return "openai"
    return "none"


def check_llm_available() -> tuple[bool, str]:
    """
    Check which backend is available and return a human-readable status.

    Returns
    -------
    (is_available: bool, message: str)
    """
    provider = get_active_provider()

    if provider == "openai":
        return True, f"✅ OpenAI sẵn sàng · Model: {OPENAI_MODEL}"

    return (
        False,
        "❌ Chưa cấu hình OpenAI. Hãy thêm OPENAI_API_KEY vào file .env.",
    )


def call_llm(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 2048,
    timeout: int | None = None,
) -> str:
    """
    Send messages to the active LLM and return the response text.

    Parameters
    ----------
    messages    : list of {"role": str, "content": str}
    temperature : sampling temperature (0–1)
    max_tokens  : maximum tokens in the response
    timeout     : request timeout in seconds

    Returns
    -------
    str – model response text

    Raises
    ------
    RuntimeError if no backend is available
    """
    provider = get_active_provider()

    if provider == "openai":
        return _call_openai(messages, temperature, max_tokens, timeout or OPENAI_TIMEOUT)

    raise RuntimeError("Chưa cấu hình OPENAI_API_KEY trong .env.")


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

def _call_openai(
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai package chưa được cài. Hãy chạy: pip install openai"
        ) from exc

    client = OpenAI(api_key=_get_openai_key(), timeout=float(timeout))
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()
