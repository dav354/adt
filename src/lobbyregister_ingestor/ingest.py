from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, ValidationError
from rich.console import Console
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .api_client import (ApiClientError, LobbyRegisterApiClient,
                         ResourceNotFoundError)
from .db_connector import DatabaseSession
from .models import IngestionConfig
from .schema_builder import ColumnInfo, TableNode

LOGGER = logging.getLogger("lobbyregister.ingestor")


class StatisticsModel(BaseModel):
    source: Optional[str] = None
    sourceDate: datetime
    jsonDocumentationUrl: Optional[str] = None

    model_config = ConfigDict(extra="allow")


# --- Nested Models for RegisterEntry ---


class RegisterEntryVersionInfo(BaseModel):
    registerEntryId: int
    jsonDetailUrl: str
    version: int
    legislation: str
    validFromDate: datetime
    validUntilDate: Optional[datetime] = None
    versionActiveLobbyist: bool


class AccountDetails(BaseModel):
    activeLobbyist: bool
    activeDateRanges: list[dict[str, datetime]]
    firstPublicationDate: datetime
    lastUpdateDate: Optional[datetime] = None
    registerEntryVersions: list[RegisterEntryVersionInfo]
    accountHasCodexViolations: bool


class SharedInfo(BaseModel):
    code: str
    de: str
    en: str


class Email(BaseModel):
    email: str


class Website(BaseModel):
    website: str


class ContactDetails(BaseModel):
    phoneNumber: Optional[str] = None
    emails: Optional[list[Email]] = None
    websites: Optional[list[Website]] = None


class Address(BaseModel):
    type: str
    street: Optional[str] = None
    streetNumber: Optional[str] = None
    zipCode: Optional[str] = None
    city: Optional[str] = None
    country: Optional[SharedInfo] = None


class LegalRepresentative(BaseModel):
    lastName: Optional[str] = None
    firstName: Optional[str] = None
    function: Optional[str] = None
    recentGovernmentFunctionPresent: Optional[bool] = None
    entrustedPerson: Optional[bool] = None
    contactDetails: Optional[dict] = None


class LobbyistIdentity(BaseModel):
    identity: str
    name: Optional[str] = None
    legalFormType: Optional[SharedInfo] = None
    legalForm: Optional[SharedInfo] = None
    contactDetails: Optional[ContactDetails] = None
    address: Optional[Address] = None
    capitalCityRepresentationPresent: Optional[bool] = None
    legalRepresentatives: Optional[list[LegalRepresentative]] = None
    entrustedPersonsPresent: Optional[bool] = None
    membersPresent: Optional[bool] = None
    membershipsPresent: bool


class ActivitiesAndInterests(BaseModel):
    activity: Optional[SharedInfo] = None
    typesOfExercisingLobbyWork: Optional[list[SharedInfo]] = None
    fieldsOfInterest: Optional[list[SharedInfo]] = None
    activityDescription: Optional[str] = None


class FiscalYearUpdate(BaseModel):
    updateMissing: bool
    lastFiscalYearUpdate: Optional[datetime] = None

class RegisterEntryDetails(BaseModel):
    registerEntryId: int
    legislation: str
    version: int
    detailsPageUrl: str
    pdfUrl: str
    validFromDate: datetime
    fiscalYearUpdate: Optional[FiscalYearUpdate] = None


# --- Main Model ---


class RegisterEntryModel(BaseModel):
    registerNumber: str
    registerEntryDetails: Optional[RegisterEntryDetails] = None
    accountDetails: Optional[AccountDetails] = None
    lobbyistIdentity: Optional[LobbyistIdentity] = None
    activitiesAndInterests: Optional[ActivitiesAndInterests] = None
    version: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class RegisterEntryVersionModel(BaseModel):

    registerNumber: str

    version: int

    model_config = ConfigDict(extra="allow")



def convert_value(column_info: ColumnInfo, value: Any) -> Any:

    schema = column_info.schema

    p_type = schema.get("type")

    fmt = schema.get("format")

    if value is None:

        return None

    if p_type == "string" and fmt == "date-time":

        if isinstance(value, datetime):

            return value

        if isinstance(value, str):

            try:

                return datetime.fromisoformat(value.replace("Z", "+00:00"))

            except ValueError:

                LOGGER.debug("Failed to parse datetime value %s", value)

                return None

    if p_type == "integer" and isinstance(value, str) and value.isdigit():

        return int(value)

    if p_type == "number" and isinstance(value, str):

        try:

            return float(value)

        except ValueError:

            return None

    if p_type == "boolean" and isinstance(value, str):

        lowered = value.strip().lower()

        if lowered in {"true", "1", "yes"}:

            return True

        if lowered in {"false", "0", "no"}:

            return False

    return value


async def persist_node(
    conn: AsyncConnection,
    node: TableNode,
    payload: Any,
    parent_id: Optional[int] = None,
) -> Optional[int]:

    if node.is_array:

        await persist_array(conn, node, payload, parent_id)

        return None

    return await persist_object(conn, node, payload, parent_id)


async def persist_array(
    conn: AsyncConnection,
    node: TableNode,
    payload: Any,
    parent_id: Optional[int],
) -> None:

    if parent_id is None:

        LOGGER.debug("Array node %s missing parent id, skipping", node.name)

        return

    if not isinstance(payload, list):

        return

    table = node.table

    await conn.execute(delete(table).where(table.c.parent_id == parent_id))

    if node.is_scalar_array:

        if node.scalar_value is None:

            return

        rows = []

        for position, item in enumerate(payload):

            converted = convert_value(node.scalar_value, item)

            rows.append(
                {
                    "parent_id": parent_id,
                    "position": position,
                    node.scalar_value.column_name: converted,
                }
            )

        if rows:

            await conn.execute(table.insert(), rows)

        return

    for position, item in enumerate(payload):

        await persist_object(
            conn,
            node,
            item,
            parent_id=parent_id,
            position=position,
            clear_existing=False,
        )


async def persist_object(
    conn: AsyncConnection,
    node: TableNode,
    payload: Any,
    parent_id: Optional[int] = None,
    position: Optional[int] = None,
    clear_existing: bool = True,
) -> Optional[int]:

    if not isinstance(payload, dict):

        return None

    table = node.table

    row: dict[str, Any] = {}

    for prop_name, column_info in node.columns.items():

        value = payload.get(prop_name)

        row[column_info.column_name] = convert_value(column_info, value)

    if parent_id is not None:

        row["parent_id"] = parent_id

    if position is not None:

        row["position"] = position

    unique_columns = [col for col in node.unique_columns if row.get(col) is not None]

    if unique_columns:

        stmt = (
            insert(table)
            .values(**row)
            .on_conflict_do_update(
                index_elements=[table.c[column] for column in unique_columns],
                set_={
                    key: value
                    for key, value in row.items()
                    if key not in unique_columns
                },
            )
            .returning(table.c.id)
        )

        result = await conn.execute(stmt)

        row_id = result.scalar_one()

    else:

        if clear_existing and parent_id is not None:

            await conn.execute(delete(table).where(table.c.parent_id == parent_id))

        result = await conn.execute(table.insert().returning(table.c.id), row)

        row_id = result.scalar_one()

    for prop_name, child in node.object_children.items():

        child_payload = payload.get(prop_name)

        await persist_node(conn, child, child_payload, parent_id=row_id)

    for prop_name, child in node.array_children.items():

        child_payload = payload.get(prop_name)

        await persist_node(conn, child, child_payload, parent_id=row_id)

    return row_id


async def run_ingestion(
    config: IngestionConfig, console: Optional[Console] = None
) -> None:

    active_console = console or Console()

    session = DatabaseSession(config.database)

    engine = await session.open()

    if config.database.apply_schema:

        LOGGER.info("Applying database schema as requested by configuration")

        await session.ensure_schema()

    root_nodes = session.root_nodes

    statistics_node = root_nodes["statistics_register_entries"]

    entries_node = root_nodes["register_entries"]

    versions_node = root_nodes["register_entry_versions"]

    semaphore = asyncio.Semaphore(max(1, config.api.max_concurrency))

    async with LobbyRegisterApiClient(config.api) as api_client:

        await ingest_statistics(active_console, api_client, engine, statistics_node)

        entries_processed = 0

        versions_processed = 0

        with active_console.status("Fetching register entries...") as status:

            async for entry_payload in api_client.iter_register_entries():

                try:

                    entry_model = RegisterEntryModel.model_validate(entry_payload)

                except ValidationError as exc:

                    LOGGER.error("Skipping entry due to validation error: %s", exc)

                    continue

                entry_dict = entry_model.model_dump()

                async with engine.begin() as conn:

                    entry_id = await persist_node(conn, entries_node, entry_dict)

                if entry_id is None:

                    continue

                entries_processed += 1

                version_tasks = []

                for version in sorted(collect_versions(entry_model)):

                    version_tasks.append(
                        asyncio.create_task(
                            fetch_and_store_version(
                                semaphore,
                                api_client,
                                engine,
                                versions_node,
                                entry_model.registerNumber,
                                version,
                            )
                        )
                    )

                if version_tasks:

                    for fut in asyncio.as_completed(version_tasks):

                        versions_processed += await fut

                if entries_processed % 25 == 0:

                    status.update(
                        f"Processed {entries_processed} entries; {versions_processed} versions"
                    )

    LOGGER.info(
        "Ingestion completed: %s entries, %s versions",
        entries_processed,
        versions_processed,
    )


async def ingest_statistics(
    console: Console,
    api_client: LobbyRegisterApiClient,
    engine: AsyncEngine,
    statistics_node: TableNode,
) -> None:

    async with engine.begin() as conn:

        with console.status("Fetching statistics..."):

            statistics_payload = await api_client.get_statistics()

        try:

            statistics_model = StatisticsModel.model_validate(statistics_payload)

        except ValidationError as exc:

            LOGGER.error("Statistics payload validation error: %s", exc)

            return

        await persist_node(conn, statistics_node, statistics_model.model_dump())


async def fetch_and_store_version(
    semaphore: asyncio.Semaphore,
    api_client: LobbyRegisterApiClient,
    engine: AsyncEngine,
    versions_node: TableNode,
    register_number: str,
    version: int,
) -> int:

    async with semaphore:

        try:

            payload = await api_client.get_register_entry_version(
                register_number, version
            )

        except ResourceNotFoundError:

            LOGGER.warning(
                "Version %s for register entry %s not found",
                version,
                register_number,
            )

            return 0

        except ApiClientError as exc:

            LOGGER.error(
                "Failed to fetch version %s for %s: %s", version, register_number, exc
            )

            return 0

    try:

        version_model = RegisterEntryModel.model_validate(payload)

    except ValidationError as exc:

        LOGGER.error(
            "Version payload validation error for %s/%s: %s",
            register_number,
            version,
            exc,
        )

        return 0

    async with engine.begin() as conn:

        await persist_node(conn, versions_node, version_model.model_dump())

    return 1


def collect_versions(entry_model: RegisterEntryModel) -> set[int]:

    versions: set[int] = set()

    if entry_model.version is not None:

        versions.add(entry_model.version)

    if entry_model.registerEntryDetails:

        versions.add(entry_model.registerEntryDetails.version)

    if entry_model.accountDetails:

        for item in entry_model.accountDetails.registerEntryVersions:

            versions.add(item.version)

    return versions
