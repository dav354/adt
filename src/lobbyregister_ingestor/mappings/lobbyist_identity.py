"""Mapping helpers for lobbyist identity structures."""

from __future__ import annotations

from typing import Any, Dict

from .common import (d, insert_address, insert_contact,
                     insert_recent_gov_function, insert_returning, scalar,
                     upsert_code_label)


def load_lobbyist_identity(cur, entry_id: int, data: Dict[str, Any]) -> None:
    if not data:
        return

    npt_id = upsert_code_label(
        cur, "natural_person_type", data.get("naturalPersonType")
    )
    lft_id = upsert_code_label(cur, "legal_form_type", data.get("legalFormType"))
    lf_id = upsert_code_label(cur, "legal_form", data.get("legalForm"))
    addr_id = insert_address(cur, data.get("address"))
    contact_id = insert_contact(cur, data.get("contactDetails"))
    recent_fn_id = insert_recent_gov_function(
        cur,
        (
            data.get("recentGovernmentFunction")
            if data.get("recentGovernmentFunctionPresent")
            else None
        ),
    )

    identity_id = insert_returning(
        cur,
        """
        INSERT INTO public.lobbyist_identity(
          entry_id, identity, natural_person_type_label_id, academic_degree_before, academic_degree_after,
          last_name, first_name, common_first_name, artist_name, company_name,
          recent_gov_function_present, recent_gov_function_id,
          address_id, contact_id, legal_form_type_label_id, legal_form_label_id, legal_form_text,
          capital_city_repr_id, entrusted_persons_present, name_text, members_present, memberships_present
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            entry_id,
            scalar(data, "identity"),
            npt_id,
            scalar(data, "academicDegreeBefore"),
            scalar(data, "academicDegreeAfter"),
            scalar(data, "lastName"),
            scalar(data, "firstName"),
            scalar(data, "commonFirstName"),
            scalar(data, "artistName"),
            scalar(data, "companyName"),
            data.get("recentGovernmentFunctionPresent"),
            recent_fn_id,
            addr_id,
            contact_id,
            lft_id,
            lf_id,
            scalar((data.get("legalForm") or {}), "legalFormText"),
            None,
            data.get("entrustedPersonsPresent"),
            scalar(data, "name"),
            data.get("membersPresent"),
            data.get("membershipsPresent"),
        ),
    )

    _load_capital_city_representation(
        cur, identity_id, data.get("capitalCityRepresentation")
    )
    _load_entrusted_persons(cur, identity_id, data.get("entrustedPersons") or [])
    _load_legal_representatives(
        cur, identity_id, data.get("legalRepresentatives") or []
    )
    _load_named_employees(cur, identity_id, data.get("namedEmployees") or [])
    _load_members_count(cur, identity_id, data.get("membersCount") or {})
    _load_memberships(cur, identity_id, data.get("memberships") or [])


def _load_capital_city_representation(
    cur, identity_id: int, payload: Dict[str, Any] | None
) -> None:
    if not payload:
        return
    address_id = insert_address(cur, payload.get("address"))
    contact_id = insert_contact(cur, payload.get("contactDetails"))
    representation_id = insert_returning(
        cur,
        "INSERT INTO public.capital_city_representation(address_id, contact_id) VALUES (%s,%s)",
        (address_id, contact_id),
    )
    cur.execute(
        "UPDATE public.lobbyist_identity SET capital_city_repr_id=%s WHERE id=%s",
        (representation_id, identity_id),
    )


def _load_entrusted_persons(
    cur, identity_id: int, persons: list[Dict[str, Any]]
) -> None:
    for ordinal, person in enumerate(persons, start=1):
        recent_fn_id = insert_recent_gov_function(
            cur,
            (
                person.get("recentGovernmentFunction")
                if person.get("recentGovernmentFunctionPresent")
                else None
            ),
        )
        cur.execute(
            """
            INSERT INTO public.entrusted_person(
              identity_id, ordinal, academic_degree_before, academic_degree_after, last_name, first_name,
              artist_name, recent_gov_function_present, recent_gov_function_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                identity_id,
                ordinal,
                scalar(person, "academicDegreeBefore"),
                scalar(person, "academicDegreeAfter"),
                scalar(person, "lastName"),
                scalar(person, "firstName"),
                scalar(person, "artistName"),
                person.get("recentGovernmentFunctionPresent"),
                recent_fn_id,
            ),
        )


def _load_legal_representatives(
    cur, identity_id: int, representatives: list[Dict[str, Any]]
) -> None:
    for ordinal, representative in enumerate(representatives, start=1):
        recent_fn_id = insert_recent_gov_function(
            cur,
            (
                representative.get("recentGovernmentFunction")
                if representative.get("recentGovernmentFunctionPresent")
                else None
            ),
        )
        contact_id = insert_contact(cur, representative.get("contact"))
        cur.execute(
            """
            INSERT INTO public.legal_representative(
              identity_id, ordinal, academic_degree_before, academic_degree_after, last_name, first_name,
              common_first_name, artist_name, function_text, recent_gov_function_id, contact_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                identity_id,
                ordinal,
                scalar(representative, "academicDegreeBefore"),
                scalar(representative, "academicDegreeAfter"),
                scalar(representative, "lastName"),
                scalar(representative, "firstName"),
                scalar(representative, "commonFirstName"),
                scalar(representative, "artistName"),
                scalar(representative, "function"),
                recent_fn_id,
                contact_id,
            ),
        )


def _load_named_employees(
    cur, identity_id: int, employees: list[Dict[str, Any]]
) -> None:
    for ordinal, employee in enumerate(employees, start=1):
        cur.execute(
            "INSERT INTO public.named_employee(identity_id, ordinal, academic_degree_before, academic_degree_after, last_name, common_first_name) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                identity_id,
                ordinal,
                scalar(employee, "academicDegreeBefore"),
                scalar(employee, "academicDegreeAfter"),
                scalar(employee, "lastName"),
                scalar(employee, "commonFirstName"),
            ),
        )


def _load_members_count(cur, identity_id: int, members: Dict[str, Any]) -> None:
    if not members:
        return
    cur.execute(
        """
        INSERT INTO public.members_count(identity_id, natural_persons, organizations, total_count, date_count)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (
            identity_id,
            members.get("naturalPersons"),
            members.get("organizations"),
            members.get("total"),
            d(scalar(members, "date")),
        ),
    )


def _load_memberships(cur, identity_id: int, memberships: list[Any]) -> None:
    for ordinal, membership in enumerate(memberships, start=1):
        cur.execute(
            "INSERT INTO public.membership(identity_id, ordinal, membership) VALUES (%s,%s,%s)",
            (
                identity_id,
                ordinal,
                (
                    membership
                    if isinstance(membership, str)
                    else scalar(membership, "membership")
                ),
            ),
        )
