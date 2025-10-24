"""Registry of mapping handlers for top-level JSON fragments."""

from __future__ import annotations

from typing import Callable, Dict, Tuple

from .account import load_account_details
from .activities import load_activities_interests
from .annual_reports import load_annual_reports
from .clients import load_client_identity
from .code_of_conduct import load_code_of_conduct
from .contracts import load_contracts
from .employees import load_employees
from .funding import (load_donators, load_financial_expenses,
                      load_main_funding_sources, load_membership_fees,
                      load_public_allowances)
from .lobbyist_identity import load_lobbyist_identity
from .register_details import load_register_entry_details
from .regulatory_projects import load_regulatory_projects
from .statements import load_statements

SectionHandler = Callable[[any, int, Dict[str, any]], None]

SECTION_HANDLERS: Tuple[Tuple[str, SectionHandler], ...] = (
    ("accountDetails", load_account_details),
    ("registerEntryDetails", load_register_entry_details),
    ("lobbyistIdentity", load_lobbyist_identity),
    ("activitiesAndInterests", load_activities_interests),
    ("clientIdentity", load_client_identity),
    ("employeesInvolvedInLobbying", load_employees),
    ("financialExpenses", load_financial_expenses),
    ("mainFundingSources", load_main_funding_sources),
    ("publicAllowances", load_public_allowances),
    ("donators", load_donators),
    ("membershipFees", load_membership_fees),
    ("annualReports", load_annual_reports),
    ("regulatoryProjects", load_regulatory_projects),
    ("statements", load_statements),
    ("contracts", load_contracts),
    ("codeOfConduct", load_code_of_conduct),
)
