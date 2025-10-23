from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy import delete, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from .schema import ScalarField, TableSpec

LOGGER = logging.getLogger("lobbyregister.ingestor.persistence")


def _as_datetime(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def convert_scalar(field: ScalarField, value: Any) -> Any:
    """Convert a JSON value into the appropriate Python type for the column."""
    if value is None:
        return None

    scalar_type = field.scalar_type
    if scalar_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return None

    if scalar_type == "integer":
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    if scalar_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    if scalar_type == "datetime":
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return _as_datetime(value)
        return None

    if isinstance(value, str):
        return value
    return str(value)


async def sync_table(
    conn: AsyncConnection,
    spec: TableSpec,
    payload: Mapping[str, Any],
    parent_id: Optional[int] = None,
    position: Optional[int] = None,
) -> Optional[int]:
    """Insert or upsert data for ``spec`` and cascade into relations."""
    if payload is None:
        return None

    row: dict[str, Any] = {}
    for field in spec.scalars.values():
        value = payload.get(field.name) if isinstance(payload, Mapping) else None
        row[field.column_name] = convert_scalar(field, value)

    if spec.parent_fk and parent_id is not None:
        row[spec.parent_fk] = parent_id
    if spec.position_column and position is not None:
        row["position"] = position

    stmt = insert(spec.table).values(**row)
    if spec.unique_columns:
        stmt = (
            pg_insert(spec.table)
            .values(**row)
            .on_conflict_do_update(
                index_elements=[spec.table.c[col] for col in spec.unique_columns],
                set_={k: row[k] for k in row if k not in spec.unique_columns},
            )
        )
    res = await conn.execute(stmt.returning(spec.table.c.id))
    row_id = res.scalar_one()
    await sync_relations(conn, spec, payload, row_id)
    return row_id


async def sync_relations(
    conn: AsyncConnection,
    spec: TableSpec,
    payload: Mapping[str, Any],
    parent_id: int,
) -> None:
    """Synchronise child relations of ``spec`` based on ``payload``."""
    if not spec.relations:
        return

    data = payload if isinstance(payload, Mapping) else {}
    for relation in spec.relations:
        child_spec = relation.target
        parent_fk = child_spec.parent_fk
        if parent_fk is None:
            LOGGER.debug("Relation %s on %s skipped (no parent FK)", relation.name, spec.name)
            continue

        await conn.execute(
            delete(child_spec.table).where(child_spec.table.c[parent_fk] == parent_id)
        )

        value = data.get(relation.name)
        if relation.relation == "one":
            if isinstance(value, Mapping):
                await sync_table(conn, child_spec, value, parent_id=parent_id)
        elif relation.relation == "many":
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                for idx, item in enumerate(value):
                    if isinstance(item, Mapping):
                        await sync_table(
                            conn,
                            child_spec,
                            item,
                            parent_id=parent_id,
                            position=idx,
                        )
        elif relation.relation == "scalar_array":
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                for idx, item in enumerate(value):
                    await sync_table(
                        conn,
                        child_spec,
                        {"value": item},
                        parent_id=parent_id,
                        position=idx,
                    )
