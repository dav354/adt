"""Mapping helpers for employee statistics."""

from __future__ import annotations

from typing import Any

from .common import d, scalar


def load_employees(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    count = data.get("employeesCount") or {}
    cur.execute(
        """
        INSERT INTO public.employees_involved(entry_id, related_year_finished, related_year_start, related_year_end,
                                              employees_from, employees_to, employee_fte)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            data.get("relatedFiscalYearFinished"),
            d(scalar(data, "relatedFiscalYearStart")),
            d(scalar(data, "relatedFiscalYearEnd")),
            count.get("from"),
            count.get("to"),
            data.get("employeeFTE"),
        ),
    )
