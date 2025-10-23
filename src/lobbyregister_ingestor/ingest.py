from __future__ import annotations

import logging
from typing import Optional

from rich.console import Console
from .api_client import ApiClientError, LobbyRegisterApiClient, ResourceNotFoundError
from .db_connector import DatabaseSession
from .models import IngestionConfig
from .persistence import sync_table

LOGGER = logging.getLogger("lobbyregister.ingestor")


async def run_ingestion(config: IngestionConfig, console: Optional[Console] = None) -> None:
    active_console = console or Console()
    session = DatabaseSession(config.database)
    engine = await session.open()
    schema = session.schema

    if config.database.apply_schema:
        LOGGER.info("Applying database schema as requested by configuration")
        await session.ensure_schema()

    processed_entries = 0
    total_expected: Optional[int] = None

    async with LobbyRegisterApiClient(config.api) as api_client:
        with active_console.status("Lade Registereinträge...") as status:
            async for summary in api_client.iter_register_entries():
                register_number = summary.get("registerNumber")
                if not register_number:
                    continue

                if total_expected is None:
                    total = summary.get("totalResultCount")
                    if isinstance(total, int) and total >= 0:
                        total_expected = total

                try:
                    entry_payload = await api_client.get_register_entry(register_number)
                    if isinstance(entry_payload, dict):
                        for meta_key in ("source", "sourceUrl", "sourceDate", "jsonDocumentationUrl"):
                            if meta_key in summary and meta_key not in entry_payload:
                                entry_payload[meta_key] = summary[meta_key]
                except ResourceNotFoundError:
                    LOGGER.warning(
                        "Registereintrag %s nicht gefunden (404), überspringe",
                        register_number,
                    )
                    continue
                except ApiClientError as exc:
                    LOGGER.error(
                        "Überspringe Registereintrag %s aufgrund API-Fehler: %s",
                        register_number,
                        exc,
                    )
                    continue

                async with engine.begin() as conn:
                    await sync_table(conn, schema.root, entry_payload)

                processed_entries += 1
                if processed_entries % 25 == 0:
                    if total_expected:
                        status.update(
                            f"{processed_entries}/{total_expected} Registereinträge verarbeitet"
                        )
                    else:
                        status.update(f"{processed_entries} Registereinträge verarbeitet")

    if total_expected:
        LOGGER.info(
            "Ingestion abgeschlossen: %s von %s Registereinträgen verarbeitet",
            processed_entries,
            total_expected,
        )
    else:
        LOGGER.info(
            "Ingestion abgeschlossen: %s Registereinträge verarbeitet",
            processed_entries,
        )
