"""
Centralized configuration.

Everything environment-specific (secrets, backend URLs, tunable
thresholds) lives here instead of scattered across modules, so deploying
to a new environment means editing one .env file, not hunting through
source.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Environment
    # "production" enables stricter startup checks -- see main.py's
    # lifespan, which refuses to start with wildcard CORS in production
    # unless explicitly overridden.
    environment: str = "development"
    allow_wildcard_cors_in_production: bool = False

    # Auth
    # Comma-separated list of valid API keys. Any request without a
    # matching `Authorization: Bearer <key>` header is rejected. In a real
    # multi-tenant deployment, replace this with per-agent keys stored in
    # a database so keys can be individually issued/revoked -- a single
    # shared secret is a reasonable starting point for one org's own
    # agents, not for a public multi-tenant service.
    api_keys: str = "dev-local-key"

    # Rate limiting
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Judge model
    judge_backend: str = "ollama"  # "ollama" or "openai"
    ollama_url: str = "http://localhost:11434/api/chat"
    ollama_model: str = "llama3.2"
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None

    # Detection thresholds
    similarity_threshold: float = 0.3
    classifier_threshold: float = 0.5
    ambiguous_low: float = 0.35
    ambiguous_high: float = 0.6

    # Request limits 
    max_request_body_bytes: int = 2_000_000  # 2 MB

    # Storage
    db_path: str = "guardrail.db"

    # CORS
    cors_origins: str = "*"

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
