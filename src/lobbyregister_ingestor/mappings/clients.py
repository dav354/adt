"""Mapping helpers for client identities."""

from __future__ import annotations

from typing import Any, Dict

from .common import (d, insert_address, insert_contact, insert_returning,
                     scalar, upsert_code_label)


def load_client_identity(cur, entry_id: int, data: Dict[str, Any]) -> None:
    if not data:
        return
    client_id = insert_returning(
        cur,
        "INSERT INTO public.client_identity(entry_id, clients_present, clients_count) VALUES (%s,%s,%s)",
        (entry_id, data.get("clientsPresent"), data.get("clientsCount")),
    )
    _insert_client_organizations(cur, client_id, data.get("clientOrganizations") or [])
    _insert_client_persons(cur, client_id, data.get("clientPersons") or [])


def _insert_client_organizations(
    cur, client_id: int, organizations: list[Dict[str, Any]]
) -> None:
    for ordinal, org in enumerate(organizations, start=1):
        address_id = insert_address(cur, org.get("address"))
        contact_id = insert_contact(cur, org.get("contactDetails"))
        lft_id = upsert_code_label(cur, "legal_form_type", org.get("legalFormType"))
        lf_id = upsert_code_label(cur, "legal_form", org.get("legalForm"))
        org_id = insert_returning(
            cur,
            """
            INSERT INTO public.client_org(client_identity_id, ordinal, reference_name, reference_details_url, name,
                                          legal_form_type_label_id, legal_form_label_id, legal_form_text,
                                          address_id, contact_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                client_id,
                ordinal,
                scalar(org, "referenceName"),
                scalar(org, "referenceDetailsPageUrl"),
                scalar(org, "name"),
                lft_id,
                lf_id,
                scalar(org.get("legalForm"), "legalFormText"),
                address_id,
                contact_id,
            ),
        )
        for idx, rep in enumerate(org.get("legalRepresentatives") or [], start=1):
            rep_contact = insert_contact(cur, rep.get("contactDetails"))
            cur.execute(
                """
                INSERT INTO public.client_org_legal_rep(client_org_id, ordinal, academic_degree_before, academic_degree_after,
                                                        common_first_name, last_name, function_text, contact_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    org_id,
                    idx,
                    scalar(rep, "academicDegreeBefore"),
                    scalar(rep, "academicDegreeAfter"),
                    scalar(rep, "commonFirstName"),
                    scalar(rep, "lastName"),
                    scalar(rep, "function"),
                    rep_contact,
                ),
            )


def _insert_client_persons(cur, client_id: int, persons: list[Dict[str, Any]]) -> None:
    for ordinal, person in enumerate(persons, start=1):
        cur.execute(
            """
            INSERT INTO public.client_person(client_identity_id, ordinal, reference_name, reference_details_url,
                                             academic_degree_before, academic_degree_after, last_name, common_first_name)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                client_id,
                ordinal,
                scalar(person, "referenceName"),
                scalar(person, "referenceDetailsPageUrl"),
                scalar(person, "academicDegreeBefore"),
                scalar(person, "academicDegreeAfter"),
                scalar(person, "lastName"),
                scalar(person, "commonFirstName"),
            ),
        )
