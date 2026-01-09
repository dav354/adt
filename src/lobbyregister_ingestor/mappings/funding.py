"""Mapping helpers for financial sections."""

from __future__ import annotations

from typing import Any

from .common import d, insert_returning, scalar, upsert_code_label, upsert_country


def load_financial_expenses(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    rng = data.get("financialExpensesEuro") or {}
    cur.execute(
        """
        INSERT INTO public.financial_expenses(entry_id, refuse_info, refuse_reason, related_year_finished,
                                              related_year_start, related_year_end, fiscal_year_completed,
                                              fiscal_year_start_ym, fiscal_year_end_ym, expenses_from_eur, expenses_to_eur)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            data.get("refuseFinancialExpensesInformation"),
            scalar(data, "refuseFinancialExpensesInformationReason"),
            data.get("relatedFiscalYearFinished"),
            d(scalar(data, "relatedFiscalYearStart")),
            d(scalar(data, "relatedFiscalYearEnd")),
            data.get("fiscalYearCompleted"),
            scalar(data, "fiscalYearStart"),
            scalar(data, "fiscalYearEnd"),
            rng.get("from"),
            rng.get("to"),
        ),
    )


def load_main_funding_sources(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    parent_id = insert_returning(
        cur,
        "INSERT INTO public.main_funding_sources(entry_id, related_year_finished, related_year_start, related_year_end) VALUES (%s,%s,%s,%s)",
        (
            entry_id,
            data.get("relatedFiscalYearFinished"),
            d(scalar(data, "relatedFiscalYearStart")),
            d(scalar(data, "relatedFiscalYearEnd")),
        ),
    )
    for ordinal, item in enumerate(data.get("mainFundingSources") or [], start=1):
        label_id = upsert_code_label(cur, "main_funding_source", item)
        cur.execute(
            "INSERT INTO public.main_funding_source_item(parent_id, ordinal, label_id) VALUES (%s,%s,%s)",
            (parent_id, ordinal, label_id),
        )


def load_public_allowances(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    parent_id = insert_returning(
        cur,
        """
        INSERT INTO public.public_allowances(entry_id, refuse_info, refuse_reason, allowances_present,
                                             related_year_finished, related_year_start, related_year_end,
                                             fiscal_year_completed, fiscal_year_start_ym, fiscal_year_end_ym)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            data.get("refusePublicAllowancesInformation"),
            scalar(data, "refusePublicAllowancesInformationReason"),
            data.get("publicAllowancesPresent"),
            data.get("relatedFiscalYearFinished"),
            d(scalar(data, "relatedFiscalYearStart")),
            d(scalar(data, "relatedFiscalYearEnd")),
            data.get("fiscalYearCompleted"),
            scalar(data, "fiscalYearStart"),
            scalar(data, "fiscalYearEnd"),
        ),
    )
    for ordinal, item in enumerate(data.get("publicAllowances") or [], start=1):
        type_id = upsert_code_label(cur, "public_allowance_type", item.get("type"))
        country_id = upsert_country(cur, item.get("country"))
        rng = item.get("publicAllowanceEuro") or {}
        cur.execute(
            """
            INSERT INTO public.public_allowance_item(parent_id, ordinal, name, type_label_id, country_id, location, amount_from_eur, amount_to_eur, description)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                parent_id,
                ordinal,
                scalar(item, "name"),
                type_id,
                country_id,
                scalar(item, "location"),
                rng.get("from"),
                rng.get("to"),
                scalar(item, "description"),
            ),
        )


def load_donators(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    parent_id = insert_returning(
        cur,
        """
        INSERT INTO public.donators(entry_id, refuse_info, refuse_reason, info_present, related_year_finished, related_year_start,
                                    related_year_end, fiscal_year_completed, fiscal_year_start_ym, fiscal_year_end_ym, total_from_eur, total_to_eur)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            data.get("refuseDonatorsInformation"),
            scalar(data, "refuseDonatorsInformationReason"),
            data.get("donatorsInformationPresent"),
            data.get("relatedFiscalYearFinished"),
            d(scalar(data, "relatedFiscalYearStart")),
            d(scalar(data, "relatedFiscalYearEnd")),
            data.get("fiscalYearCompleted"),
            scalar(data, "fiscalYearStart"),
            scalar(data, "fiscalYearEnd"),
            (data.get("totalDonationsEuro") or {}).get("from"),
            (data.get("totalDonationsEuro") or {}).get("to"),
        ),
    )
    for ordinal, donor in enumerate(data.get("donators") or [], start=1):
        rng = donor.get("donationEuro") or {}
        cur.execute(
            "INSERT INTO public.donator_item(parent_id, ordinal, name, amount_from_eur, amount_to_eur, description) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                parent_id,
                ordinal,
                scalar(donor, "name"),
                rng.get("from"),
                rng.get("to"),
                scalar(donor, "description"),
            ),
        )


def load_membership_fees(cur, entry_id: int, data: dict[str, Any]) -> None:
    if not data:
        return
    parent_id = insert_returning(
        cur,
        """
        INSERT INTO public.membership_fees(entry_id, related_year_finished, related_year_start, related_year_end,
                                           total_from_eur, total_to_eur, individual_contributors_present)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            data.get("relatedFiscalYearFinished"),
            d(scalar(data, "relatedFiscalYearStart")),
            d(scalar(data, "relatedFiscalYearEnd")),
            (data.get("totalMembershipFees") or {}).get("from"),
            (data.get("totalMembershipFees") or {}).get("to"),
            data.get("individualContributorsPresent"),
        ),
    )
    for ordinal, contributor in enumerate(
        data.get("individualContributors") or [], start=1
    ):
        cur.execute(
            "INSERT INTO public.individual_contributor(fees_id, ordinal, name) VALUES (%s,%s,%s)",
            (parent_id, ordinal, scalar(contributor, "name")),
        )
