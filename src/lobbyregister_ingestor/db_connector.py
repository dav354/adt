from __future__ import annotations

import asyncio
import logging
import time
from importlib import resources
from typing import Any, Dict, Optional

import yaml
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .models import DatabaseConfig
from .schema_builder import (SchemaBuildResult, TableNode,
                             build_schema_from_openapi)

LOGGER = logging.getLogger("lobbyregister.ingestor.db")
DEFAULT_SPEC_RESOURCE = "api-docs-lobbyregister.yaml"


class DatabaseSession:
    """Manage the SQLAlchemy engine and cached OpenAPI-derived schema."""

    def __init__(
        self,
        config: DatabaseConfig,
        spec_resource: str = DEFAULT_SPEC_RESOURCE,
    ) -> None:
        self._config = config
        self._spec_resource = spec_resource
        self._engine: Optional[AsyncEngine] = None
        self._schema_result: Optional[SchemaBuildResult] = None

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

    def _load_spec(self) -> Dict[str, Any]:
        with (
            resources.files("lobbyregister_ingestor")
            .joinpath(self._spec_resource)
            .open("r", encoding="utf-8") as fh
        ):
            return yaml.safe_load(fh)

    def _ensure_schema_loaded(self) -> None:
        if self._schema_result is None:
            self._schema_result = build_schema_from_openapi(self._load_spec())

    async def ensure_schema(self) -> None:
        if self._engine is None:
            raise RuntimeError("Engine not initialised; call open() first")
        self._ensure_schema_loaded()
        async with self._engine.begin() as conn:
            await conn.run_sync(self._schema_result.metadata.create_all)

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Engine not initialised; call open()")
        return self._engine

    @property
    def root_nodes(self) -> Dict[str, TableNode]:
        self._ensure_schema_loaded()
        if self._schema_result is None:
            raise RuntimeError("Schema not initialised; call open() first")
        return self._schema_result.root_nodes

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._schema_result = None
