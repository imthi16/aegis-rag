"""Ollama LLM wrapper (CLAUDE.md §6.11).

Async client talking to the local Ollama server (in-network only; zero egress).
Grading/faithfulness callers pass ``format="json"`` + temperature 0.0. The
``ollama`` import is lazy so this module loads without the package (graph nodes
that monkeypatch get_llm in tests do not need a live server).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from app.core.config import get_settings


def _extract_content(resp: Any) -> str:
    """Read the message content from either a dict or a pydantic response."""
    message = resp["message"] if isinstance(resp, dict) else resp.message
    content = message["content"] if isinstance(message, dict) else message.content
    return str(content)


class LLM:
    def __init__(self) -> None:
        import ollama  # lazy

        settings = get_settings()
        self._client = ollama.AsyncClient(
            host=settings.ollama_host,
            timeout=settings.ollama_request_timeout_s,
        )
        self._model = settings.ollama_model
        self._keep_alive = settings.ollama_keep_alive

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        num_ctx: int,
        format: Literal["", "json"] = "",
    ) -> str:
        resp = await self._client.chat(
            model=self._model,
            messages=messages,
            options={"temperature": temperature, "num_ctx": num_ctx},
            format=format or None,
            keep_alive=self._keep_alive,
        )
        return _extract_content(resp)


@lru_cache
def get_llm() -> LLM:
    return LLM()


async def ping_llm() -> bool:
    """Readiness check: can we reach the Ollama server? (health.py)."""
    try:
        import ollama

        settings = get_settings()
        client = ollama.AsyncClient(
            host=settings.ollama_host, timeout=settings.ollama_request_timeout_s
        )
        await client.list()
        return True
    except Exception:
        return False
