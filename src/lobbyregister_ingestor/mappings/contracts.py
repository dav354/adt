"""Mapping helpers for contracts."""

from __future__ import annotations

from typing import Any, Dict

from .common import (d, insert_address, insert_contact,
                     insert_recent_gov_function, insert_returning, scalar,
                     upsert_code_label)


def load_contracts(cur, entry_id: int, data: Dict[str, Any]) -> None:
    if not data:
        return
    parent_id = insert_returning(
        cur,
        "INSERT INTO public.contracts(entry_id, contracts_present, contracts_count) VALUES (%s,%s,%s)",
        (entry_id, data.get("contractsPresent"), data.get("contractsCount")),
    )
    for ordinal, contract in enumerate(data.get("contracts") or [], start=1):
        _insert_contract(cur, parent_id, ordinal, contract)


def _insert_contract(
    cur, parent_id: int, ordinal: int, contract: Dict[str, Any]
) -> None:
    item_id = insert_returning(
        cur,
        "INSERT INTO public.contract_item(parent_id, ordinal, description) VALUES (%s,%s,%s)",
        (parent_id, ordinal, scalar(contract, "description")),
    )
    for idx, field in enumerate(contract.get("fieldsOfInterest") or [], start=1):
        label_id = upsert_code_label(cur, "field_of_interest", field)
        cur.execute(
            "INSERT INTO public.contract_field_of_interest(contract_item_id, ordinal, label_id, field_of_interest_text) VALUES (%s,%s,%s,%s)",
            (item_id, idx, label_id, scalar(field, "fieldOfInterestText")),
        )
    for idx, reference in enumerate(contract.get("regulatoryProjects") or [], start=1):
        cur.execute(
            "INSERT INTO public.contract_reg_project_ref(contract_item_id, ordinal, regulatory_project_number, regulatory_project_title) VALUES (%s,%s,%s,%s)",
            (
                item_id,
                idx,
                scalar(reference, "regulatoryProjectNumber"),
                scalar(reference, "regulatoryProjectTitle"),
            ),
        )
    _insert_contract_clients(cur, item_id, contract.get("clients") or {})
    _insert_contract_contractors(cur, item_id, contract.get("contractors") or {})


def _insert_contract_clients(
    cur, contract_item_id: int, payload: Dict[str, Any]
) -> None:
    clients_id = insert_returning(
        cur,
        "INSERT INTO public.contract_clients(contract_item_id) VALUES (%s)",
        (contract_item_id,),
    )
    for idx, org in enumerate(payload.get("clientOrganizations") or [], start=1):
        address_id = insert_address(cur, org.get("address"))
        contact_id = insert_contact(cur, org.get("contactDetails"))
        lft_id = upsert_code_label(cur, "legal_form_type", org.get("legalFormType"))
        lf_id = upsert_code_label(cur, "legal_form", org.get("legalForm"))
        org_id = insert_returning(
            cur,
            """
            INSERT INTO public.contract_client_org(clients_id, ordinal, reference_name, reference_details_url, name,
                                                   legal_form_type_label_id, legal_form_label_id, legal_form_text,
                                                   address_id, contact_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                clients_id,
                idx,
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
        for rep_idx, rep in enumerate(org.get("legalRepresentatives") or [], start=1):
            cur.execute(
                """
                INSERT INTO public.contract_client_org_legal_rep(client_org_id, ordinal, academic_degree_before, academic_degree_after,
                                                                 first_name, last_name, artist_name, function_text)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    org_id,
                    rep_idx,
                    scalar(rep, "academicDegreeBefore"),
                    scalar(rep, "academicDegreeAfter"),
                    scalar(rep, "firstName"),
                    scalar(rep, "lastName"),
                    scalar(rep, "artistName"),
                    scalar(rep, "function"),
                ),
            )
        _insert_financial_resources(
            cur,
            "INSERT INTO public.contract_client_org_financial_resources(client_org_id, last_fiscal_year_finished, last_fiscal_year_start, last_fiscal_year_end, amount_from_eur, amount_to_eur) VALUES (%s,%s,%s,%s,%s,%s)",
            org_id,
            payload=org.get("financialResourcesReceived") or {},
        )

    for idx, person in enumerate(payload.get("clientPersons") or [], start=1):
        person_id = insert_returning(
            cur,
            """
            INSERT INTO public.contract_client_person(clients_id, ordinal, reference_name, reference_details_url,
                                                      academic_degree_before, academic_degree_after,
                                                      last_name, first_name, artist_name, company_name)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                clients_id,
                idx,
                scalar(person, "referenceName"),
                scalar(person, "referenceDetailsPageUrl"),
                scalar(person, "academicDegreeBefore"),
                scalar(person, "academicDegreeAfter"),
                scalar(person, "lastName"),
                scalar(person, "firstName"),
                scalar(person, "artistName"),
                scalar(person, "companyName"),
            ),
        )
        _insert_financial_resources(
            cur,
            "INSERT INTO public.contract_client_person_financial_resources(client_person_id, last_fiscal_year_finished, last_fiscal_year_start, last_fiscal_year_end, amount_from_eur, amount_to_eur) VALUES (%s,%s,%s,%s,%s,%s)",
            person_id,
            payload=person.get("financialResourcesReceived") or {},
        )


def _insert_contract_contractors(
    cur, contract_item_id: int, payload: Dict[str, Any]
) -> None:
    contractors_id = insert_returning(
        cur,
        "INSERT INTO public.contract_contractors(contract_item_id, lobbying_is_carried_out_by_lobbyist) VALUES (%s,%s)",
        (
            contract_item_id,
            payload.get("lobbyingIsCarriedOutByLobbyist"),
        ),
    )
    for idx, person in enumerate(payload.get("entrustedPersons") or [], start=1):
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
            INSERT INTO public.contractor_entrusted_person(
              contractors_id, ordinal, academic_degree_before, academic_degree_after, first_name, last_name,
              artist_name, function_text, recent_gov_function_present, recent_gov_function_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                contractors_id,
                idx,
                scalar(person, "academicDegreeBefore"),
                scalar(person, "academicDegreeAfter"),
                scalar(person, "firstName"),
                scalar(person, "lastName"),
                scalar(person, "artistName"),
                scalar(person, "function"),
                person.get("recentGovernmentFunctionPresent"),
                recent_fn_id,
            ),
        )

    for idx, org in enumerate(payload.get("contractorOrganizations") or [], start=1):
        address_id = insert_address(cur, org.get("address"))
        contact_id = insert_contact(cur, org.get("contactDetails"))
        ccr = org.get("capitalCityRepresentation") or {}
        ccr_address = insert_address(cur, ccr.get("address")) if ccr else None
        ccr_contact = insert_contact(cur, ccr.get("contactDetails")) if ccr else None
        lft_id = upsert_code_label(cur, "legal_form_type", org.get("legalFormType"))
        lf_id = upsert_code_label(cur, "legal_form", org.get("legalForm"))
        org_id = insert_returning(
            cur,
            """
            INSERT INTO public.contractor_org(
              contractors_id, ordinal, reference_name, reference_details_url, name,
              legal_form_type_label_id, legal_form_label_id, legal_form_text,
              address_id, contact_id, capital_city_repr_address_id, capital_city_repr_contact_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                contractors_id,
                idx,
                scalar(org, "referenceName"),
                scalar(org, "referenceDetailsPageUrl"),
                scalar(org, "name"),
                lft_id,
                lf_id,
                scalar(org.get("legalForm"), "legalFormText"),
                address_id,
                contact_id,
                ccr_address,
                ccr_contact,
            ),
        )
        for rep_idx, representative in enumerate(
            org.get("legalRepresentatives") or [], start=1
        ):
            recent_fn_id = insert_recent_gov_function(
                cur,
                (
                    representative.get("recentGovernmentFunction")
                    if representative.get("recentGovernmentFunctionPresent")
                    else None
                ),
            )
            cur.execute(
                """
                INSERT INTO public.contractor_org_legal_rep(
                  contractor_org_id, ordinal, academic_degree_before, academic_degree_after,
                  first_name, last_name, artist_name, function_text,
                  recent_gov_function_present, recent_gov_function_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    org_id,
                    rep_idx,
                    scalar(representative, "academicDegreeBefore"),
                    scalar(representative, "academicDegreeAfter"),
                    scalar(representative, "firstName"),
                    scalar(representative, "lastName"),
                    scalar(representative, "artistName"),
                    scalar(representative, "function"),
                    representative.get("recentGovernmentFunctionPresent"),
                    recent_fn_id,
                ),
            )
        for rep_idx, assigned in enumerate(org.get("assignedPersons") or [], start=1):
            recent_fn_id = insert_recent_gov_function(
                cur,
                (
                    assigned.get("recentGovernmentFunction")
                    if assigned.get("recentGovernmentFunctionPresent")
                    else None
                ),
            )
            cur.execute(
                """
                INSERT INTO public.assigned_person(
                  contractors_id, ordinal, academic_degree_before, academic_degree_after,
                  first_name, last_name, artist_name,
                  recent_gov_function_present, recent_gov_function_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    contractors_id,
                    rep_idx,
                    scalar(assigned, "academicDegreeBefore"),
                    scalar(assigned, "academicDegreeAfter"),
                    scalar(assigned, "firstName"),
                    scalar(assigned, "lastName"),
                    scalar(assigned, "artistName"),
                    assigned.get("recentGovernmentFunctionPresent"),
                    recent_fn_id,
                ),
            )

    for idx, person in enumerate(payload.get("contractorPersons") or [], start=1):
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
            INSERT INTO public.contractor_person(
              contractors_id, ordinal, reference_name, reference_details_url, academic_degree_before, academic_degree_after,
              last_name, first_name, artist_name, company_name, recent_gov_function_present, recent_gov_function_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                contractors_id,
                idx,
                scalar(person, "referenceName"),
                scalar(person, "referenceDetailsPageUrl"),
                scalar(person, "academicDegreeBefore"),
                scalar(person, "academicDegreeAfter"),
                scalar(person, "lastName"),
                scalar(person, "firstName"),
                scalar(person, "artistName"),
                scalar(person, "companyName"),
                person.get("recentGovernmentFunctionPresent"),
                recent_fn_id,
            ),
        )


def _insert_financial_resources(
    cur, sql: str, parent_id: int, payload: Dict[str, Any]
) -> None:
    if not payload:
        return
    if not any(
        payload.get(key)
        for key in (
            "lastFiscalYearFinished",
            "lastFiscalYearStart",
            "lastFiscalYearEnd",
            "from",
            "to",
        )
    ):
        return
    cur.execute(
        sql,
        (
            parent_id,
            payload.get("lastFiscalYearFinished"),
            d(scalar(payload, "lastFiscalYearStart")),
            d(scalar(payload, "lastFiscalYearEnd")),
            payload.get("from"),
            payload.get("to"),
        ),
    )
