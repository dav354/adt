"""Mapping helpers for activities and interests."""

from __future__ import annotations

from typing import Any, Dict

from .common import insert_returning, scalar, upsert_code_label


def load_activities_interests(cur, entry_id: int, data: Dict[str, Any]) -> None:
    if not data:
        return
    activity_label_id = upsert_code_label(cur, "activity", data.get("activity"))
    activities_id = insert_returning(
        cur,
        """
        INSERT INTO public.activities_interests(entry_id, activity_label_id, activity_text, activity_legal_basis,
                                                activity_operation_type, activity_description)
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            activity_label_id,
            scalar(data.get("activity"), "activityText"),
            scalar(data.get("activity"), "activityLegalBasis"),
            scalar(data, "activityOperationType"),
            scalar(data, "activityDescription"),
        ),
    )
    for ordinal, item in enumerate(
        data.get("typesOfExercisingLobbyWork") or [], start=1
    ):
        label_id = upsert_code_label(cur, "exercising_type", item)
        cur.execute(
            "INSERT INTO public.activity_exercising_type(activities_id, ordinal, label_id) VALUES (%s,%s,%s)",
            (activities_id, ordinal, label_id),
        )
    for ordinal, field in enumerate(data.get("fieldsOfInterest") or [], start=1):
        label_id = upsert_code_label(cur, "field_of_interest", field)
        cur.execute(
            "INSERT INTO public.field_of_interest(activities_id, ordinal, label_id, field_of_interest_text) VALUES (%s,%s,%s,%s)",
            (activities_id, ordinal, label_id, scalar(field, "fieldOfInterestText")),
        )
    for ordinal, project in enumerate(data.get("legislativeProjects") or [], start=1):
        cur.execute(
            "INSERT INTO public.legislative_project(activities_id, ordinal, name, printing_number, document_title, document_url) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                activities_id,
                ordinal,
                scalar(project, "name"),
                scalar(project, "printingNumber"),
                scalar(project, "documentTitle"),
                scalar(project, "documentUrl"),
            ),
        )
