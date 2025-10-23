from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

from .api_client import ApiClientError
from .ingest import run_ingestion
from .models import (DEFAULT_API_BACKOFF_FACTOR, DEFAULT_API_BACKOFF_MAX,
                     DEFAULT_API_KEY, DEFAULT_API_MAX_CONCURRENCY,
                     DEFAULT_API_MAX_RETRIES, DEFAULT_API_TIMEOUT,
                     DEFAULT_API_URL, DEFAULT_DB_CONNECT_TIMEOUT,
                     DEFAULT_SCHEMA_RESOURCE, ApiConfig, DatabaseConfig,
                     IngestionConfig)

console = Console()
LOGGER = logging.getLogger("lobbyregister.ingestor")


def configure_logging() -> None:
    """Configure root logging to use Rich's styled output."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = RichHandler(
        console=console, rich_tracebacks=False, show_path=False, markup=False
    )
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
        force=True,
    )


def load_config() -> IngestionConfig:
    """Load ingestion configuration from environment variables."""
    load_dotenv()

    pg_user = os.getenv("POSTGRES_USER")
    pg_password = os.getenv("POSTGRES_PASSWORD")
    pg_db = os.getenv("POSTGRES_DB")
    pg_host = os.getenv("POSTGRES_HOST", os.getenv("PGHOST", "localhost"))
    pg_port = os.getenv("POSTGRES_PORT", os.getenv("PGPORT", "5432"))
    if not (pg_user and pg_password and pg_db):
        raise RuntimeError(
            "POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB environment variables are required"
        )
    database_url = (
        f"postgresql+asyncpg://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
    )

    api_url = os.getenv("LOBBY_API_URL", DEFAULT_API_URL)
    api_timeout = float(os.getenv("LOBBY_API_TIMEOUT", str(DEFAULT_API_TIMEOUT)))
    api_key = os.getenv("LOBBY_API_KEY", DEFAULT_API_KEY).strip()
    if not api_key:
        raise RuntimeError("LOBBY_API_KEY environment variable must not be empty")

    api_max_retries = int(
        os.getenv("LOBBY_API_MAX_RETRIES", str(DEFAULT_API_MAX_RETRIES))
    )
    api_backoff_factor = float(
        os.getenv("LOBBY_API_BACKOFF_FACTOR", str(DEFAULT_API_BACKOFF_FACTOR))
    )
    api_backoff_max = float(
        os.getenv("LOBBY_API_BACKOFF_MAX", str(DEFAULT_API_BACKOFF_MAX))
    )
    api_max_concurrency = int(
        os.getenv("LOBBY_API_MAX_CONCURRENCY", str(DEFAULT_API_MAX_CONCURRENCY))
    )

    connect_timeout = float(
        os.getenv("DATABASE_CONNECT_TIMEOUT", str(DEFAULT_DB_CONNECT_TIMEOUT))
    )
    apply_schema = os.getenv("DATABASE_APPLY_SCHEMA", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    schema_resource = os.getenv("DATABASE_SCHEMA_RESOURCE", DEFAULT_SCHEMA_RESOURCE)

    return IngestionConfig(
        api=ApiConfig(
            url=api_url,
            timeout=api_timeout,
            api_key=api_key,
            max_retries=api_max_retries,
            backoff_factor=api_backoff_factor,
            backoff_max=api_backoff_max,
            max_concurrency=api_max_concurrency,
        ),
        database=DatabaseConfig(
            url=database_url,
            connect_timeout=connect_timeout,
            apply_schema=apply_schema,
            schema_resource=schema_resource,
        ),
    )


def main() -> None:
    configure_logging()
    try:
        config = load_config()
    except Exception as exc:  # pragma: no cover - guard for CLI usage
        LOGGER.error("Configuration error: %s", exc)
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(run_ingestion(config, console=console))
    except ApiClientError as exc:
        LOGGER.exception("Lobbyregister API error")
        print(f"API error: {exc}", file=sys.stderr)
        sys.exit(2)
    except httpx.RequestError as exc:
        LOGGER.exception("HTTP error while accessing the Lobbyregister API")
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # pragma: no cover - guard for CLI usage
        LOGGER.exception("Ingestion failed")
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
