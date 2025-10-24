"""
Utilities to bootstrap the PostgreSQL schema for the lobbyregister ingestor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import psycopg

DEFAULT_SCHEMA_PATH = Path(__file__).with_name("scheme.sql")


def schema_exists(dsn: str, table: str = "public.register_entry") -> bool:
    """Return True if the sentinel table already exists."""
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (table,))
            return cur.fetchone()[0] is not None


def apply_schema(dsn: str, sql_path: Optional[Path] = None) -> bool:
    """
    Execute the schema SQL file against the given database.

    Returns True if the schema was applied, False if it already existed.
    """
    path = sql_path or DEFAULT_SCHEMA_PATH
    ddl = path.read_text(encoding="utf-8")

    if schema_exists(dsn):
        return False

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)

        pg_user = psycopg.conninfo.conninfo_to_dict(dsn).get("user")
        if pg_user:
            try:
                with conn.cursor() as cur:
                    # Set searchpath to public for grafana
                    cur.execute(f"ALTER ROLE {pg_user} SET search_path TO public")
            except psycopg.Error:
                pass

    return True
