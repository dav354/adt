"""Mapping helpers for regulatory projects."""

from __future__ import annotations

from typing import Any

from .common import d, insert_returning, scalar, upsert_code_label


def load_regulatory_projects(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    parent_id = insert_returning(
        cur,
        "INSERT INTO public.regulatory_projects(entry_id, projects_present, projects_count) VALUES (%s,%s,%s)",
        (
            entry_id,
            data.get("regulatoryProjectsPresent"),
            data.get("regulatoryProjectsCount"),
        ),
    )
    for ordinal, project in enumerate(data.get("regulatoryProjects") or [], start=1):
        _insert_project(cur, parent_id, ordinal, project)


def _insert_project(cur, parent_id: int, ordinal: int, project: dict[str, Any]) -> None:
    item_id = insert_returning(
        cur,
        """
        INSERT INTO public.regulatory_project_item(parent_id, ordinal, regulatory_project_number, title, printed_matters_present, draft_bill_present, description)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            parent_id,
            ordinal,
            scalar(project, "regulatoryProjectNumber"),
            scalar(project, "title"),
            project.get("printedMattersPresent"),
            project.get("draftBillPresent"),
            scalar(project, "description"),
        ),
    )
    for idx, matter in enumerate(project.get("printedMatters") or [], start=1):
        _insert_printed_matter(cur, item_id, idx, matter)
    draft_bill = project.get("draftBill")
    if project.get("draftBillPresent") and draft_bill:
        _insert_draft_bill(cur, item_id, draft_bill)
    for idx, field in enumerate(project.get("fieldsOfInterest") or [], start=1):
        label_id = upsert_code_label(cur, "field_of_interest", field)
        cur.execute(
            "INSERT INTO public.reg_project_field_of_interest(project_item_id, ordinal, label_id) VALUES (%s,%s,%s)",
            (item_id, idx, label_id),
        )
    for idx, law in enumerate(project.get("affectedLaws") or [], start=1):
        cur.execute(
            "INSERT INTO public.reg_project_affected_law(project_item_id, ordinal, title, short_title, url) VALUES (%s,%s,%s,%s,%s)",
            (
                item_id,
                idx,
                scalar(law, "title"),
                scalar(law, "shortTitle"),
                scalar(law, "url"),
            ),
        )


def _insert_printed_matter(
    cur, project_item_id: int, ordinal: int, matter: dict[str, Any]
) -> None:
    matter_id = insert_returning(
        cur,
        "INSERT INTO public.reg_project_printed_matter(project_item_id, ordinal, title, printing_number, issuer, document_url, project_url) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (
            project_item_id,
            ordinal,
            scalar(matter, "title"),
            scalar(matter, "printingNumber"),
            scalar(matter, "issuer"),
            scalar(matter, "documentUrl"),
            scalar(matter, "projectUrl"),
        ),
    )
    for idx, ministry in enumerate(matter.get("leadingMinistries") or [], start=1):
        ministry_id = _insert_leading_ministry(cur, ministry)
        cur.execute(
            "INSERT INTO public.reg_project_printed_matter_ministry(printed_matter_id, ordinal, ministry_id) VALUES (%s,%s,%s)",
            (matter_id, idx, ministry_id),
        )
    migrated = matter.get("migratedDraftBill")
    if migrated:
        migrated_id = insert_returning(
            cur,
            "INSERT INTO public.migrated_draft_bill(printed_matter_id, title, publication_date) VALUES (%s,%s,%s)",
            (
                matter_id,
                scalar(migrated, "title"),
                d(scalar(migrated, "publicationDate")),
            ),
        )
        for idx, ministry in enumerate(
            migrated.get("leadingMinistries") or [], start=1
        ):
            ministry_id = _insert_leading_ministry(cur, ministry)
            cur.execute(
                """
                INSERT INTO public.migrated_draft_bill_ministry(migrated_db_id, ordinal, ministry_id, draft_bill_document_url, draft_bill_project_url)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    migrated_id,
                    idx,
                    ministry_id,
                    scalar(ministry, "draftBillDocumentUrl"),
                    scalar(ministry, "draftBillProjectUrl"),
                ),
            )


def _insert_draft_bill(cur, project_item_id: int, payload: dict[str, Any]) -> None:
    draft_id = insert_returning(
        cur,
        "INSERT INTO public.draft_bill(project_item_id, title, publication_date, custom_title, custom_date) VALUES (%s,%s,%s,%s,%s)",
        (
            project_item_id,
            scalar(payload, "title"),
            d(scalar(payload, "publicationDate")),
            scalar(payload, "customTitle"),
            d(scalar(payload, "customDate")),
        ),
    )
    for idx, ministry in enumerate(payload.get("leadingMinistries") or [], start=1):
        ministry_id = _insert_leading_ministry(cur, ministry)
        cur.execute(
            "INSERT INTO public.draft_bill_ministry(draft_bill_id, ordinal, ministry_id) VALUES (%s,%s,%s)",
            (draft_id, idx, ministry_id),
        )


def _insert_leading_ministry(cur, ministry: dict[str, Any]) -> int:
    return insert_returning(
        cur,
        "INSERT INTO public.leading_ministry(title, short_title, url, election_period) VALUES (%s,%s,%s,%s)",
        (
            scalar(ministry, "title"),
            scalar(ministry, "shortTitle"),
            scalar(ministry, "url"),
            ministry.get("electionPeriod"),
        ),
    )
