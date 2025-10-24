"""Mapping helpers for annual reports."""

from __future__ import annotations

from typing import Any, Dict

from .common import d, scalar


def load_annual_reports(cur, entry_id: int, data: Dict[str, Any]) -> None:
    if not data:
        return
    cur.execute(
        """
        INSERT INTO public.annual_reports(entry_id, disclosure_requirements_exist, refuse_annual_fin_stmt,
          refuse_annual_fin_stmt_reason, annual_report_exists, annual_report_last_fy_exists,
          annual_report_prev_last_fy_exists, finished_fy_exists, last_fy_start, last_fy_end,
          prev_last_fy_start, prev_last_fy_end, annual_report_pdf_url, missing_annual_report_reason,
          report_was_published_elsewhere, location_of_report_publication)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            data.get("disclosureRequirementsExist"),
            data.get("refuseAnnualFinanceStatement"),
            scalar(data, "refuseAnnualFinanceStatementReason"),
            data.get("annualReportExists"),
            data.get("annualReportLastFiscalYearExists"),
            data.get("annualReportPreviousLastFiscalYearExists"),
            data.get("finishedFiscalYearExists"),
            d(scalar(data, "lastFiscalYearStart")),
            d(scalar(data, "lastFiscalYearEnd")),
            d(scalar(data, "previousLastFiscalYearStart")),
            d(scalar(data, "previousLastFiscalYearEnd")),
            scalar(data, "annualReportPdfUrl"),
            scalar(data, "missingAnnualReportReason"),
            data.get("reportWasPublishedElsewhere"),
            scalar(data, "locationOfReportPublication"),
        ),
    )
