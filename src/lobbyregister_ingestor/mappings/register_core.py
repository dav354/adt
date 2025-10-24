"""Core register_entry helpers."""

from __future__ import annotations

from typing import Dict

from .common import dt, scalar


def upsert_register_entry(cur, doc: Dict[str, object]) -> int:
    cur.execute(
        """
        INSERT INTO public.register_entry (schema_uri, source, source_url, source_date, json_doc_url, register_number)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (register_number) DO UPDATE SET
          schema_uri=EXCLUDED.schema_uri,
          source=EXCLUDED.source,
          source_url=EXCLUDED.source_url,
          source_date=EXCLUDED.source_date,
          json_doc_url=EXCLUDED.json_doc_url
        RETURNING id
        """,
        (
            doc.get("$schema"),
            scalar(doc, "source"),
            scalar(doc, "sourceUrl"),
            dt(scalar(doc, "sourceDate")),
            scalar(doc, "jsonDocumentationUrl"),
            scalar(doc, "registerNumber"),
        ),
    )
    return cur.fetchone()["id"]


TOP_LEVEL_TABLES = [
    "account_details",
    "register_entry_details",
    "lobbyist_identity",
    "activities_interests",
    "client_identity",
    "employees_involved",
    "financial_expenses",
    "main_funding_sources",
    "public_allowances",
    "donators",
    "membership_fees",
    "annual_reports",
    "regulatory_projects",
    "statements",
    "contracts",
    "code_of_conduct",
]


def purge_children_for_entry(cur, entry_id: int) -> None:
    for table in TOP_LEVEL_TABLES:
        cur.execute(f"DELETE FROM public.{table} WHERE entry_id=%s", (entry_id,))
