"""Application configuration — the single ingress for every environment variable.

Per CLAUDE.md §6.1: every env var in §4 is exposed here with a type and default.
No other module may read ``os.environ`` directly. In ``production`` the app must
refuse to boot if a required secret is missing/blank or still equal to its
``CHANGE_ME_*`` placeholder (Golden Rule 9 — fail closed).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that must never survive into a production boot.
_PLACEHOLDER_PREFIX = "CHANGE_ME"


class Settings(BaseSettings):
    """Typed view over the process environment (CLAUDE.md §4)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────────────
    app_env: Literal["production", "development", "test"] = "production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_name: str = "aegis-rag"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    rate_limit_per_minute: int = 60
    request_max_body_mb: int = 50

    # ── Postgres ────────────────────────────────────────
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "aegis"
    postgres_user: str = "aegis_app"
    postgres_password: str = "CHANGE_ME_STRONG_PASSWORD"
    database_url: str | None = None
    audit_db_user: str = "aegis_audit"
    audit_db_password: str = "CHANGE_ME_AUDIT_PASSWORD"

    # ── Ollama (LLM) ────────────────────────────────────
    ollama_host: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:32b"
    ollama_num_ctx: int = 8192
    ollama_temperature_gen: float = 0.1
    ollama_temperature_grade: float = 0.0
    ollama_request_timeout_s: int = 180
    ollama_keep_alive: str = "30m"

    # ── Embeddings (BGE-M3) ─────────────────────────────
    embedding_model_path: str = "/models/bge-m3"
    embedding_dim: int = 1024
    embedding_device: Literal["cpu", "cuda"] = "cpu"
    embedding_batch_size: int = 16
    embedding_max_length: int = 8192
    embedding_normalize: bool = True

    # ── Reranker (bge-reranker-v2-m3) ───────────────────
    reranker_model_path: str = "/models/bge-reranker-v2-m3"
    reranker_device: Literal["cpu", "cuda"] = "cpu"
    reranker_use_fp16: bool = True
    reranker_batch_size: int = 16

    # ── Retrieval / Fusion / CRAG ───────────────────────
    faiss_index_path: str = "/data/faiss/index.faiss"
    faiss_index_type: Literal["flat_ip", "hnsw"] = "flat_ip"
    faiss_hnsw_m: int = 32
    faiss_hnsw_ef_search: int = 128
    bm25_index_path: str = "/data/bm25/bm25.pkl"
    retrieval_top_k: int = 40
    rrf_k: int = 60
    rerank_top_n: int = 8
    overfetch_factor: int = 3
    crag_relevance_threshold: float = 0.5
    crag_min_relevant_docs: int = 2
    faithfulness_threshold: float = 0.7
    max_correction_attempts: int = 1
    max_regen_attempts: int = 1

    # ── Chunking ────────────────────────────────────────
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    allowed_file_types: str = "pdf,docx,txt,md,html"
    upload_max_size_mb: int = 50
    # Where uploaded originals are retained so a document can be re-parsed and
    # re-embedded by /documents/{id}/reindex. Backed by the same volume as the
    # indexes; never leaves the perimeter.
    document_storage_path: str = "/data/documents"

    # ── Auth (JWT) ──────────────────────────────────────
    jwt_secret_key: str = "CHANGE_ME_64_CHAR_RANDOM_HEX"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    password_hash_scheme: str = "argon2"

    # ── Audit (tamper-evident) ──────────────────────────
    audit_hmac_key: str = "CHANGE_ME_64_CHAR_RANDOM_HEX"
    audit_chain_genesis_hash: str = "0" * 64

    # ── Offline enforcement (DO NOT CHANGE) ─────────────
    hf_hub_offline: str = "1"
    transformers_offline: str = "1"
    hf_datasets_offline: str = "1"

    # ── Frontend (Vite, build-time) ─────────────────────
    vite_api_base_url: str = "/api/v1"

    # ── Derived / parsed views ──────────────────────────
    @property
    def cors_origins_list(self) -> list[str]:
        """``CORS_ORIGINS`` parsed comma-separated → list (CLAUDE.md §6.1)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_file_types_list(self) -> list[str]:
        """``ALLOWED_FILE_TYPES`` parsed comma-separated → lowercase list."""
        return [t.strip().lower() for t in self.allowed_file_types.split(",") if t.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @field_validator("audit_chain_genesis_hash")
    @classmethod
    def _validate_genesis(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdefABCDEF" for c in v):
            raise ValueError("AUDIT_CHAIN_GENESIS_HASH must be 64 hex chars")
        return v.lower()

    @model_validator(mode="after")
    def _build_and_validate(self) -> Settings:
        """Build ``DATABASE_URL`` from parts; reject placeholders in production."""
        # Build DATABASE_URL from parts when not explicitly provided/blank.
        if not self.database_url or not self.database_url.strip():
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )

        if self.is_production:
            self._reject_placeholder("JWT_SECRET_KEY", self.jwt_secret_key)
            self._reject_placeholder("AUDIT_HMAC_KEY", self.audit_hmac_key)
            self._reject_placeholder("POSTGRES_PASSWORD", self.postgres_password)
            # Defense in depth: an explicitly-supplied DATABASE_URL must not
            # smuggle a placeholder secret past the checks above.
            if _PLACEHOLDER_PREFIX in (self.database_url or ""):
                raise ValueError(
                    "DATABASE_URL contains a CHANGE_ME placeholder; refusing to "
                    "boot in production"
                )

        return self

    @staticmethod
    def _reject_placeholder(name: str, value: str) -> None:
        if value is None or not str(value).strip():
            raise ValueError(f"{name} must be set in production (got empty value)")
        if str(value).startswith(_PLACEHOLDER_PREFIX):
            raise ValueError(
                f"{name} still holds its CHANGE_ME placeholder; set a real secret "
                "before booting in production"
            )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide, cached settings instance (single ingress)."""
    return Settings()  # values sourced from env/.env
