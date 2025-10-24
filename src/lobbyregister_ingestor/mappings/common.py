"""Shared utilities for mapping JSON data into the relational schema."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional, Sequence

from dateutil import parser as dtparse


def dt(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return dtparse.parse(value).isoformat()
    except Exception:
        return value


def d(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return dtparse.parse(value).date().isoformat()
    except Exception:
        return value


def scalar(obj: Optional[Dict[str, Any]], key: str, default: Any = None) -> Any:
    if not isinstance(obj, dict):
        return default
    value = obj.get(key, default)
    return (
        value
        if isinstance(value, (str, int, float, bool)) or value is None
        else default
    )


def insert_returning(cur, sql: str, params: Sequence[Any]) -> int:
    cur.execute(sql + " RETURNING id", params)
    return cur.fetchone()["id"]


def upsert_code_label(cur, domain: str, obj: Optional[Dict[str, Any]]) -> Optional[int]:
    if not obj:
        return None

    code, de, en = scalar(obj, "code"), scalar(obj, "de"), scalar(obj, "en")
    if code is None and not (de or en):
        return None

    key = code or (de or en or "UNKNOWN")
    cur.execute(
        """
        INSERT INTO public.code_label(domain, code, de, en)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (domain, code) DO NOTHING
        RETURNING id, de, en
        """,
        (domain, key, de, en),
    )
    inserted = cur.fetchone()
    if inserted:
        return inserted["id"]

    cur.execute(
        "SELECT id, de, en FROM public.code_label WHERE domain=%s AND code=%s",
        (domain, key),
    )
    existing = cur.fetchone()
    if not existing:
        raise RuntimeError(f"code_label lookup failed for {(domain, key)}")

    needs_update = False
    if de and not existing["de"]:
        needs_update = True
    if en and not existing["en"]:
        needs_update = True

    if needs_update:
        cur.execute(
            """
            UPDATE public.code_label
            SET
                de = COALESCE(public.code_label.de, %s),
                en = COALESCE(public.code_label.en, %s)
            WHERE id=%s
            RETURNING id
            """,
            (de, en, existing["id"]),
        )
        return cur.fetchone()["id"]

    return existing["id"]


def upsert_country(cur, obj: Optional[Dict[str, Any]]) -> Optional[int]:
    if not obj:
        return None
    code, de, en = scalar(obj, "code"), scalar(obj, "de"), scalar(obj, "en")
    if not (code or de or en):
        return None
    cur.execute(
        """
        INSERT INTO public.country_label(code, de, en)
        VALUES (%s,%s,%s)
        ON CONFLICT (code) DO NOTHING
        RETURNING id, de, en
        """,
        (code, de, en),
    )
    inserted = cur.fetchone()
    if inserted:
        return inserted["id"]

    cur.execute(
        "SELECT id, de, en FROM public.country_label WHERE code=%s",
        (code,),
    )
    existing = cur.fetchone()
    if not existing:
        raise RuntimeError(f"country_label lookup failed for {code}")

    needs_update = False
    if de and not existing["de"]:
        needs_update = True
    if en and not existing["en"]:
        needs_update = True

    if needs_update:
        cur.execute(
            """
            UPDATE public.country_label
            SET
              de = COALESCE(public.country_label.de, %s),
              en = COALESCE(public.country_label.en, %s)
            WHERE id=%s
            RETURNING id
            """,
            (de, en, existing["id"]),
        )
        return cur.fetchone()["id"]

    return existing["id"]


def insert_address(cur, addr: Optional[Dict[str, Any]]) -> Optional[int]:
    if not addr:
        return None
    country_id = upsert_country(cur, addr.get("country"))
    return insert_returning(
        cur,
        """
        INSERT INTO public.address(kind, national_additional1, national_additional2,
                                   international_additional1, international_additional2,
                                   street, street_number, zip_code, city, post_box, country_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            scalar(addr, "type"),
            scalar(addr, "nationalAdditional1"),
            scalar(addr, "nationalAdditional2"),
            scalar(addr, "internationalAdditional1"),
            scalar(addr, "internationalAdditional2"),
            scalar(addr, "street"),
            scalar(addr, "streetNumber"),
            scalar(addr, "zipCode"),
            scalar(addr, "city"),
            scalar(addr, "postBox"),
            country_id,
        ),
    )


def insert_contact(cur, contact: Optional[Dict[str, Any]]) -> Optional[int]:
    if not contact:
        return None
    phone = scalar(contact, "phoneNumber") or scalar(contact, "phone")
    contact_id = insert_returning(
        cur, "INSERT INTO public.contact(phone_number) VALUES (%s)", (phone,)
    )

    _insert_simple_collection(
        cur,
        "INSERT INTO public.contact_email(contact_id, ordinal, email) VALUES (%s,%s,%s)",
        contact_id,
        contact.get("emails") or [],
        "email",
    )
    _insert_simple_collection(
        cur,
        "INSERT INTO public.contact_website(contact_id, ordinal, website) VALUES (%s,%s,%s)",
        contact_id,
        contact.get("websites") or [],
        "website",
    )
    return contact_id


def _insert_simple_collection(
    cur, sql: str, parent_id: int, items: Iterable[Any], key: str
) -> None:
    if isinstance(items, list):
        for ordinal, item in enumerate(items, start=1):
            if isinstance(item, dict):
                value = item.get(key)
            else:
                value = item
            if value:
                cur.execute(sql, (parent_id, ordinal, value))
    else:
        if isinstance(items, dict):
            value = items.get(key)
        else:
            value = items
        if value:
            cur.execute(sql, (parent_id, 1, value))


def insert_recent_gov_function(cur, rgf: Optional[Dict[str, Any]]) -> Optional[int]:
    if not rgf:
        return None
    type_id = upsert_code_label(cur, "recent_gov_function_type", rgf.get("type"))
    end_year_month = normalize_year_month(rgf.get("endDate"))
    rgf_id = insert_returning(
        cur,
        "INSERT INTO public.recent_government_function(ended, end_year_month, type_label_id) VALUES (%s,%s,%s)",
        (rgf.get("ended"), end_year_month, type_id),
    )

    house = rgf.get("houseOfRepresentatives")
    if isinstance(house, dict) and house.get("function"):
        fn_id = upsert_code_label(cur, "house_reps_function", house.get("function"))
        cur.execute(
            "INSERT INTO public.recent_gov_house_reps(recent_gov_fn_id, function_label_id, function_position) VALUES (%s,%s,%s)",
            (rgf_id, fn_id, scalar(house, "functionPosition")),
        )

    federal_gov = rgf.get("federalGovernment")
    if isinstance(federal_gov, dict) and federal_gov.get("function"):
        fn_id = upsert_code_label(
            cur, "federal_gov_function", federal_gov.get("function")
        )
        department = federal_gov.get("department") or {}
        dep_id = (
            insert_returning(
                cur,
                "INSERT INTO public.department(title, short_title, url, election_period) VALUES (%s,%s,%s,%s)",
                (
                    scalar(department, "title"),
                    scalar(department, "shortTitle"),
                    scalar(department, "url"),
                    department.get("electionPeriod"),
                ),
            )
            if department
            else None
        )
        cur.execute(
            "INSERT INTO public.recent_gov_federal_gov(recent_gov_fn_id, function_label_id, department_id) VALUES (%s,%s,%s)",
            (rgf_id, fn_id, dep_id),
        )

    federal_admin = rgf.get("federalAdministration")
    if isinstance(federal_admin, dict):
        cur.execute(
            """
            INSERT INTO public.recent_gov_federal_admin(
                recent_gov_fn_id, supreme_federal_authority, supreme_federal_authority_short,
                supreme_federal_authority_elect_prd, function_text)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (
                rgf_id,
                scalar(federal_admin, "supremeFederalAuthority"),
                scalar(federal_admin, "supremeFederalAuthorityShort"),
                federal_admin.get("supremeFederalAuthorityElectionPeriod"),
                scalar(federal_admin, "function"),
            ),
        )

    return rgf_id


YEAR_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def normalize_year_month(value: Any) -> Optional[str]:
    """Return a YYYY-MM string when possible, otherwise None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if YEAR_MONTH_RE.fullmatch(text):
        return text
    try:
        parsed = dtparse.parse(text)
    except Exception:
        return None
    candidate = f"{parsed.year:04d}-{parsed.month:02d}"
    return candidate if YEAR_MONTH_RE.fullmatch(candidate) else None
