"""Mapping helpers for register entry details."""

from __future__ import annotations

from typing import Any

from .common import dt, insert_returning, scalar


def load_register_entry_details(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    details_id = insert_returning(
        cur,
        """
        INSERT INTO public.register_entry_details(
          entry_id, register_entry_id_num, legislation, version, details_page_url,
          pdf_url, valid_from_date, valid_until_date, refused_anything)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            data.get("registerEntryId"),
            scalar(data, "legislation"),
            data.get("version"),
            scalar(data, "detailsPageUrl"),
            scalar(data, "pdfUrl"),
            dt(scalar(data, "validFromDate")),
            dt(scalar(data, "validUntilDate")),
            data.get("refusedAnything"),
        ),
    )
    annual_update = data.get("annualUpdate") or {}
    if annual_update:
        cur.execute(
            "INSERT INTO public.register_entry_annual_update(details_id, update_missing, last_annual_update) VALUES (%s,%s,%s)",
            (
                details_id,
                annual_update.get("updateMissing"),
                dt(scalar(annual_update, "lastAnnualUpdate")),
            ),
        )
    fiscal_update = data.get("fiscalYearUpdate") or {}
    if fiscal_update:
        cur.execute(
            "INSERT INTO public.register_entry_fiscal_year_update(details_id, update_missing, last_fiscal_year_update) VALUES (%s,%s,%s)",
            (
                details_id,
                fiscal_update.get("updateMissing"),
                dt(scalar(fiscal_update, "lastFiscalYearUpdate")),
            ),
        )
