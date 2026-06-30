"""Local-model wiring for the evaluation suite (CLAUDE.md §6.16).

CRITICAL (Golden Rule 2): RAGAS defaults to OpenAI; every metric MUST be passed
the local Ollama LLM + local BGE-M3 embeddings. The hallucination / faithfulness
suite is computed by a built-in evaluator (``app.eval.deepeval_runner``) driven
by the local JSON grader below — the third-party ``deepeval`` package is
intentionally NOT used: it carries a telemetry/tracking layer and eagerly imports
cloud-model backends, both of which violate the zero-egress rule. Heavy imports
are lazy so the package loads without ragas / langchain-community / ollama.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.config import get_settings
from app.embeddings.embedder import get_embedder

# A grader takes chat messages and returns the model's raw (JSON) reply.
Grader = Callable[[list[dict[str, str]]], str]


def get_ragas_llm() -> Any:
    """LangChain ChatOllama pinned to the local server, temperature 0."""
    from langchain_community.chat_models import ChatOllama

    settings = get_settings()
    return ChatOllama(
        base_url=settings.ollama_host,
        model=settings.ollama_model,
        temperature=0.0,
    )


def get_ragas_embeddings() -> Any:
    """Local BGE-M3 wrapped as a LangChain Embeddings (no network)."""
    from langchain_core.embeddings import Embeddings

    settings = get_settings()

    class _LocalEmbeddings(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            arr = get_embedder().encode(texts, settings.embedding_batch_size)
            return [[float(x) for x in row] for row in arr]

        def embed_query(self, text: str) -> list[float]:
            return [float(x) for x in get_embedder().encode_query(text)]

    return _LocalEmbeddings()


def get_local_grader() -> Grader:
    """Synchronous JSON grader backed by the local Ollama server (temperature 0).

    Powers the built-in evaluator (``app.eval.deepeval_runner``). Returns a
    callable that takes chat messages and returns the model's raw JSON reply.
    No third-party eval package, no egress — same offline guarantee as the rest
    of the platform.
    """
    import ollama

    settings = get_settings()
    client = ollama.Client(host=settings.ollama_host)

    def _grade(messages: list[dict[str, str]]) -> str:
        resp = client.chat(
            model=settings.ollama_model,
            messages=messages,
            options={
                "temperature": settings.ollama_temperature_grade,
                "num_ctx": settings.ollama_num_ctx,
            },
            format="json",
        )
        message = resp["message"] if isinstance(resp, dict) else resp.message
        content = message["content"] if isinstance(message, dict) else message.content
        return str(content)

    return _grade
