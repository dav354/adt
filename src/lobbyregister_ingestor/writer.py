"""Orchestrates mapping JSON documents into the relational schema."""

from __future__ import annotations

from typing import Any

from .mappings.register_core import purge_children_for_entry, upsert_register_entry
from .mappings.registry import SECTION_HANDLERS


def ingest_entry(cur, doc: dict[str, Any]) -> int:
    entry_id = upsert_register_entry(cur, doc)
    purge_children_for_entry(cur, entry_id)

    for key, handler in SECTION_HANDLERS:
        payload = doc.get(key)
        data = payload if isinstance(payload, dict) else {}
        handler(cur, entry_id, data)

    return entry_id
