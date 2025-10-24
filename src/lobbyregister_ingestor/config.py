"""Configuration loading for the lobbyregister ingestor."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _float(value: Optional[str], default: float) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    db_dsn: str
    api_base: str
    api_key: Optional[str]
    search_path: str
    detail_path: str
    query: Optional[str]
    page_size: int
    http_concurrency: int
    ingest_concurrency: int
    db_pool_size: int
    log_level: str
    http_timeout: float
    progress_every: int
    ingest_queue_size: int
    http_max_retries: int
    http_backoff_factor: float
    http_backoff_max: float

    @classmethod
    def from_env(cls) -> "Settings":
        pg_dsn = os.getenv("PG_DSN")
        if not pg_dsn:
            # If no full DSN is provided, compose one from the individual POSTGRES_* vars.
            # This keeps local development simple while still allowing a single PG_DSN override.
            db = os.getenv("POSTGRES_DB", "lobby")
            user = os.getenv("POSTGRES_USER", "postgres")
            password = os.getenv("POSTGRES_PASSWORD", "postgres")
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            pg_dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"

        api_base = os.getenv(
            "LOBBY_API_URL", "https://api.lobbyregister.bundestag.de/rest/v2"
        ).rstrip("/")

        return cls(
            db_dsn=pg_dsn,
            api_base=api_base,
            api_key=os.getenv("LOBBY_API_KEY") or None,
            # Search + detail path are intentionally lstrip-ed so callers can pass either
            # "search/detail" or "/search/detail" without breaking URL composition.
            search_path=os.getenv("ENDPOINT_SEARCH", "search/detail").lstrip("/"),
            detail_path=os.getenv("ENDPOINT_DETAIL", "register-entry/{id}").lstrip("/"),
            query=os.getenv("LOBBY_QUERY") or None,
            page_size=_int(os.getenv("PAGE_SIZE"), 100),
            http_concurrency=max(1, _int(os.getenv("HTTP_CONCURRENCY"), 8)),
            ingest_concurrency=max(1, _int(os.getenv("DB_WORKERS"), 4)),
            db_pool_size=max(1, _int(os.getenv("DB_POOL_SIZE"), 4)),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            http_timeout=_float(os.getenv("HTTP_TIMEOUT"), 60.0),
            progress_every=max(1, _int(os.getenv("PROGRESS_EVERY"), 25)),
            # Queue size bounds the number of detail payloads buffered between fetchers and DB writers.
            ingest_queue_size=max(1, _int(os.getenv("INGEST_QUEUE_SIZE"), 100)),
            http_max_retries=max(0, _int(os.getenv("HTTP_MAX_RETRIES"), 3)),
            http_backoff_factor=_float(os.getenv("HTTP_BACKOFF_FACTOR"), 0.5),
            http_backoff_max=_float(os.getenv("HTTP_BACKOFF_MAX"), 8.0),
        )
