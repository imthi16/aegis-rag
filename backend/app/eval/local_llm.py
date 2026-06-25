"""Local-model wiring for RAGAS + DeepEval (CLAUDE.md §6.16).

CRITICAL (Golden Rule 2): RAGAS and DeepEval default to OpenAI. Every metric MUST
be passed the local Ollama LLM + local BGE-M3 embeddings. Nothing here may reach
an external API. Heavy imports are lazy so the package loads without ragas /
deepeval / langchain-community installed.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.embeddings.embedder import get_embedder


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


def get_deepeval_model() -> Any:
    """DeepEval custom LLM backed by the local Ollama server."""
    from deepeval.models.base_model import DeepEvalBaseLLM

    settings = get_settings()

    class _OllamaDeepEval(DeepEvalBaseLLM):  # type: ignore[misc]  # untyped base
        def load_model(self) -> Any:
            import ollama

            return ollama.Client(host=settings.ollama_host)

        def generate(self, prompt: str) -> str:
            client = self.load_model()
            resp = client.chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0},
            )
            return str(resp["message"]["content"])

        async def a_generate(self, prompt: str) -> str:
            return self.generate(prompt)

        def get_model_name(self) -> str:
            return settings.ollama_model

    return _OllamaDeepEval()
