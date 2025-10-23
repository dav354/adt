from __future__ import annotations

import asyncio
import logging
import time
from importlib import resources
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .models import DatabaseConfig
from .schema import SchemaSpec, load_schema

LOGGER = logging.getLogger("lobbyregister.ingestor.db")
DEFAULT_SCHEME_RESOURCE = "scheme.json"


class DatabaseSession:
    """Manage the SQLAlchemy engine and cached OpenAPI-derived schema."""

    def __init__(
        self,
        config: DatabaseConfig,
        scheme_resource: str | None = None,
    ) -> None:
        self._config = config
        self._scheme_resource = scheme_resource or config.schema_resource
        self._engine: Optional[AsyncEngine] = None
        self._schema: Optional[SchemaSpec] = None

    async def open(self) -> AsyncEngine:
        if self._engine is not None:
            return self._engine

        deadline = time.time() + self._config.connect_timeout
        attempts = 0
        while True:
            attempts += 1
            try:
                LOGGER.info("Creating SQLAlchemy engine (attempt %s)", attempts)
                async_engine = create_async_engine(self._config.url, future=True)
                async with async_engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                self._engine = async_engine
                LOGGER.info("Connected to database")
                break
            except OperationalError as exc:
                if time.time() >= deadline:
                    raise RuntimeError("Database connection timed out") from exc
                LOGGER.warning("Database not ready yet (%s), retrying...", exc)
                await asyncio.sleep(min(2 * attempts, 10))

        self._ensure_schema_loaded()
        return self._engine

    def _load_scheme(self) -> SchemaSpec:
        if self._schema is not None:
            return self._schema
        with resources.as_file(
            resources.files("lobbyregister_ingestor").joinpath(self._scheme_resource)
        ) as scheme_path:
            self._schema = load_schema(Path(scheme_path))
        return self._schema

    def _ensure_schema_loaded(self) -> SchemaSpec:
        return self._load_scheme()

    async def ensure_schema(self) -> None:
        if self._engine is None:
            raise RuntimeError("Engine not initialised; call open() first")
        schema = self._ensure_schema_loaded()
        async with self._engine.begin() as conn:
            await conn.run_sync(schema.metadata.create_all)

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Engine not initialised; call open()")
        return self._engine

    @property
    def schema(self) -> SchemaSpec:
        schema = self._ensure_schema_loaded()
        if schema is None:
            raise RuntimeError("Schema not initialised; call open() first")
        return schema

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._schema = None
