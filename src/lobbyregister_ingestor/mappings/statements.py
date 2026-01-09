"""Mapping helpers for statements."""

from __future__ import annotations

from typing import Any

from .common import d, insert_returning, scalar, upsert_code_label


def load_statements(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    parent_id = insert_returning(
        cur,
        "INSERT INTO public.statements(entry_id, statements_present, statements_count) VALUES (%s,%s,%s)",
        (entry_id, data.get("statementsPresent"), data.get("statementsCount")),
    )
    for ordinal, statement in enumerate(data.get("statements") or [], start=1):
        recipient_groups = statement.get("recipientGroups") or []
        sending_date_source = recipient_groups[0] if recipient_groups else {}
        item_id = insert_returning(
            cur,
            """
            INSERT INTO public.statement_item(parent_id, ordinal, statement_number, regulatory_project_number, regulatory_project_title,
                                              pdf_url, pdf_page_count, copyright_acknowledgement,
                                              text_body, sending_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                parent_id,
                ordinal,
                scalar(statement, "statementNumber"),
                scalar(statement, "regulatoryProjectNumber"),
                scalar(statement, "regulatoryProjectTitle"),
                scalar(statement, "pdfUrl"),
                statement.get("pdfPageCount"),
                scalar(statement.get("text"), "copyrightAcknowledgement"),
                scalar(statement.get("text"), "text"),
                d(scalar(sending_date_source, "sendingDate")),
            ),
        )
        _insert_recipient_groups(cur, item_id, recipient_groups)


def _insert_recipient_groups(cur, item_id: int, groups: list[dict[str, Any]]) -> None:
    for group_idx, group in enumerate(groups, start=1):
        group_id = insert_returning(
            cur,
            "INSERT INTO public.statement_recipient_group(statement_item_id, ordinal) VALUES (%s,%s)",
            (item_id, group_idx),
        )
        recipients = group.get("recipients") or {}
        for idx, label in enumerate(recipients.get("parliament") or [], start=1):
            label_id = upsert_code_label(cur, "recipient_parliament", label)
            cur.execute(
                "INSERT INTO public.statement_recipient_parliament(group_id, ordinal, label_id) VALUES (%s,%s,%s)",
                (group_id, idx, label_id),
            )
        for idx, fed in enumerate(recipients.get("federalGovernment") or [], start=1):
            department = (fed or {}).get("department") or {}
            department_id = insert_returning(
                cur,
                "INSERT INTO public.department(title, short_title, url, election_period) VALUES (%s,%s,%s,%s)",
                (
                    scalar(department, "title"),
                    scalar(department, "shortTitle"),
                    scalar(department, "url"),
                    department.get("electionPeriod"),
                ),
            )
            cur.execute(
                "INSERT INTO public.statement_recipient_federal_gov(group_id, ordinal, department_id) VALUES (%s,%s,%s)",
                (group_id, idx, department_id),
            )
