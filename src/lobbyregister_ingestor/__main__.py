"""CLI entry point for the lobbyregister ingestion pipeline."""

from __future__ import annotations

import asyncio
import itertools
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg import errors as pg_errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg_pool.errors import PoolClosed

from .api import ApiError, LobbyregisterClient, ResourceNotFoundError
from .config import Settings
from .logging_utils import get_logger, setup_logging
from .schema_init import apply_schema
from .writer import ingest_entry


def register_number_from(
    detail: dict[str, Any], fallback: str | None = None
) -> str | None:
    return detail.get("registerNumber") or fallback or detail.get("register_number")


TRANSIENT_DB_ERRORS: tuple[type[BaseException], ...] = (
    pg_errors.DeadlockDetected,
    pg_errors.LockNotAvailable,
    pg_errors.SerializationFailure,
    pg_errors.TransactionRollback,
    pg_errors.ConnectionException,
    pg_errors.AdminShutdown,
    pg_errors.CrashShutdown,
    pg_errors.CannotConnectNow,
    pg_errors.OperatorIntervention,
    pg_errors.QueryCanceled,
)


def _is_transient_db_error(exc: BaseException) -> bool:
    return isinstance(exc, TRANSIENT_DB_ERRORS)


MAX_DB_WRITE_RETRIES = 3


def apply_optimizations(dsn: str) -> None:
    """
    Applies additional performance optimizations (indexes, materialized views)
    defined in optimization.sql, if the file exists.
    """
    logger = get_logger(__name__)
    opt_path = Path(__file__).parent / "optimization.sql"

    if not opt_path.exists():
        logger.debug("No optimization.sql found, skipping optimizations.")
        return

    logger.info("Applying optimizations from %s...", opt_path.name)
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(opt_path.read_text(encoding="utf-8"))


async def run_ingestion(settings: Settings, pool: ConnectionPool | None) -> int:
    logger = get_logger(__name__)
    counter_lock = asyncio.Lock()
    queue: asyncio.Queue = asyncio.Queue(maxsize=settings.ingest_queue_size)
    stop_token = object()

    processed = 0
    total_hint: int | None = None
    sequence_counter = itertools.count(1)

    def write_document(document: dict[str, Any]) -> None:
        if pool is None:
            return
        with pool.connection() as conn:
            try:
                with conn.cursor(row_factory=dict_row) as cur:
                    ingest_entry(cur, document)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    async def consumer_worker(worker_id: int) -> None:
        nonlocal processed, total_hint
        logger.debug("Consumer %s started.", worker_id)
        while True:
            item = await queue.get()
            if item is stop_token:
                queue.task_done()
                logger.debug("Consumer %s stopping.", worker_id)
                break

            seq, detail = item
            register_number = register_number_from(detail)

            success = False

            for attempt in range(1, MAX_DB_WRITE_RETRIES + 2):
                try:
                    await asyncio.to_thread(write_document, detail)
                except Exception as exc:
                    transient = _is_transient_db_error(exc)
                    if transient and attempt <= MAX_DB_WRITE_RETRIES:
                        logger.warning(
                            "Transient DB error for registerNumber=%s (attempt %s/%s): %s",
                            register_number,
                            attempt,
                            MAX_DB_WRITE_RETRIES + 1,
                            exc.__class__.__name__,
                        )
                        continue

                    logger.error(
                        "Database write failed #%s for registerNumber=%s after %s attempts: %s",
                        seq,
                        register_number,
                        attempt,
                        exc,
                        exc_info=True,
                    )
                    break
                else:
                    success = True
                    break

            if not success:
                queue.task_done()
                continue

            async with counter_lock:
                potential_total = detail.get("totalResultCount") or detail.get(
                    "total_count"
                )
                if potential_total and not total_hint:
                    with suppress(TypeError, ValueError):
                        total_hint = int(potential_total)
                processed += 1
                if settings.progress_every and (
                    processed % settings.progress_every == 0
                ):
                    logger.info(
                        "Processed %s/%s",
                        processed,
                        total_hint if total_hint is not None else "unknown",
                    )
            queue.task_done()

    async with LobbyregisterClient(settings) as client:
        try:
            stats = await client.get_statistics()
        except ResourceNotFoundError:
            logger.warning(
                "Statistics endpoint not available; proceeding without totals."
            )
            stats = {}
        except ApiError as exc:
            logger.warning("Failed to read statistics: %s", exc)
            stats = {}

        total_hint_candidate = (
            stats.get("totalResultCount")
            or stats.get("totalCount")
            or stats.get("registerEntriesTotalCount")
        )
        try:
            total_hint = (
                int(total_hint_candidate) if total_hint_candidate is not None else None
            )
        except (TypeError, ValueError):
            total_hint = None
        if total_hint:
            logger.info("Statistics report %s total entries.", total_hint)

        seen_registers: set[str] = set()

        async def producer() -> None:
            try:
                async for entry in client.iter_register_entries(settings.query):
                    register_number = entry.get("registerNumber")
                    if register_number and register_number in seen_registers:
                        continue
                    if register_number:
                        seen_registers.add(register_number)
                    seq = next(sequence_counter)
                    await queue.put((seq, entry))
            except ResourceNotFoundError:
                logger.warning(
                    "Register entries endpoint returned 404; nothing to ingest."
                )
            except ApiError as exc:
                logger.error("Ingestion aborted due to API error: %s", exc)
                raise
            finally:
                for _ in range(settings.ingest_concurrency):
                    await queue.put(stop_token)

        consumers = [
            asyncio.create_task(consumer_worker(i))
            for i in range(settings.ingest_concurrency)
        ]

        producer_task = asyncio.create_task(producer())
        try:
            await producer_task
        except BaseException:
            await asyncio.gather(*consumers, return_exceptions=True)
            raise
        else:
            await asyncio.gather(*consumers)

    return processed


async def async_main() -> int:
    load_dotenv()
    settings = Settings.from_env()
    setup_logging(settings.log_level)

    logger = get_logger(__name__)
    logger.debug("Using settings: %s", settings)

    if apply_schema(settings.db_dsn):
        logger.info("Initialized database schema from scheme.sql.")

    # 1. Apply additional optimizations (Indexes, MVs) defined in optimization.sql
    try:
        apply_optimizations(settings.db_dsn)
    except Exception as exc:
        logger.warning("Failed to apply optimizations: %s", exc)

    pool = ConnectionPool(
        conninfo=settings.db_dsn,
        min_size=1,
        max_size=settings.db_pool_size,
    )
    pool.wait()
    try:
        processed = await run_ingestion(settings, pool)

        # 2. Refresh Materialized Views if new data was ingested
        if processed > 0:
            logger.info("Refreshing materialized views...")
            with pool.connection() as conn:
                # Postgres Syntax: REFRESH MATERIALIZED VIEW view_name; (no IF EXISTS support)
                try:
                    conn.execute("REFRESH MATERIALIZED VIEW public.mv_financial_tops;")
                except pg_errors.UndefinedTable:
                    logger.warning(
                        "Materialized view 'public.mv_financial_tops' does not exist, skipping refresh."
                    )
                # Add other views here if you create more
            logger.info("Views refreshed.")

    except ApiError as exc:
        logger.error("Ingestion aborted due to API error: %s", exc)
        return 1
    finally:
        pool.close()
        with suppress(PoolClosed):
            pool.wait()

    logger.info("Ingestion complete. Processed %s entries.", processed)
    return 0


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning("Interrupted by user.")


if __name__ == "__main__":
    main()
