"""Mapping helpers for account details."""

from __future__ import annotations

from typing import Any, Dict

from .common import dt, insert_returning, scalar


def load_account_details(cur, entry_id: int, data: Dict[str, Any]) -> None:
    if not data:
        return
    account_id = insert_returning(
        cur,
        """
        INSERT INTO public.account_details(
          entry_id, active_lobbyist, inactive_lobbyist_start, first_publication_date,
          last_update_date, account_has_codex_violations
        ) VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            data.get("activeLobbyist"),
            dt(scalar(data, "inactiveLobbyistStartDate")),
            dt(scalar(data, "firstPublicationDate")),
            dt(scalar(data, "lastUpdateDate")),
            data.get("accountHasCodexViolations"),
        ),
    )

    for ordinal, rng in enumerate(data.get("activeDateRanges") or [], start=1):
        cur.execute(
            "INSERT INTO public.account_active_range(account_id, ordinal, from_date, until_date) VALUES (%s,%s,%s,%s)",
            (
                account_id,
                ordinal,
                dt(scalar(rng, "fromDate")),
                dt(scalar(rng, "untilDate")),
            ),
        )
    for ordinal, rng in enumerate(data.get("inactiveDateRanges") or [], start=1):
        cur.execute(
            "INSERT INTO public.account_inactive_range(account_id, ordinal, from_date, until_date) VALUES (%s,%s,%s,%s)",
            (
                account_id,
                ordinal,
                dt(scalar(rng, "fromDate")),
                dt(scalar(rng, "untilDate")),
            ),
        )
    for ordinal, version in enumerate(data.get("registerEntryVersions") or [], start=1):
        cur.execute(
            """
            INSERT INTO public.account_register_entry_version(
                account_id, ordinal, register_entry_id_num, json_detail_url, version,
                legislation, valid_from_date, valid_until_date, active_until_date, version_active_lobbyist)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                account_id,
                ordinal,
                version.get("registerEntryId"),
                scalar(version, "jsonDetailUrl"),
                version.get("version"),
                scalar(version, "legislation"),
                dt(scalar(version, "validFromDate")),
                dt(scalar(version, "validUntilDate")),
                dt(scalar(version, "activeUntilDate")),
                version.get("versionActiveLobbyist"),
            ),
        )
    for ordinal, violation in enumerate(data.get("codexViolations") or [], start=1):
        name = scalar(violation, "codexViolationName")
        if name:
            cur.execute(
                "INSERT INTO public.codex_violation(account_id, ordinal, name) VALUES (%s,%s,%s)",
                (account_id, ordinal, name),
            )
