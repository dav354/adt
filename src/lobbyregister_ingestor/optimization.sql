-- ============================================================
-- Lobbyregister Optimizations: Indexes & Views for Dashboards
-- ============================================================

-- 1) FK/Join Indexes (keeps plans simple and fast)
CREATE INDEX IF NOT EXISTS idx_address_country ON public.address(country_id);
CREATE INDEX IF NOT EXISTS idx_address_city ON public.address(city);
CREATE INDEX IF NOT EXISTS idx_contact_email_contact ON public.contact_email(contact_id);
CREATE INDEX IF NOT EXISTS idx_contact_website_contact ON public.contact_website(contact_id);

-- Accounts / entry metadata
CREATE INDEX IF NOT EXISTS idx_account_details_entry ON public.account_details(entry_id);
CREATE INDEX IF NOT EXISTS idx_account_active_account ON public.account_active_range(account_id);
CREATE INDEX IF NOT EXISTS idx_account_inactive_account ON public.account_inactive_range(account_id);
CREATE INDEX IF NOT EXISTS idx_account_rev_account ON public.account_register_entry_version(account_id);
CREATE INDEX IF NOT EXISTS idx_codex_violation_account ON public.codex_violation(account_id);
CREATE INDEX IF NOT EXISTS idx_entry_details_entry ON public.register_entry_details(entry_id);
CREATE INDEX IF NOT EXISTS idx_entry_annual_details ON public.register_entry_annual_update(details_id);
CREATE INDEX IF NOT EXISTS idx_entry_fiscal_details ON public.register_entry_fiscal_year_update(details_id);

-- Identity & people
CREATE INDEX IF NOT EXISTS idx_identity_entry ON public.lobbyist_identity(entry_id);
CREATE INDEX IF NOT EXISTS idx_identity_recent_gov ON public.lobbyist_identity(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_identity_capital_city_repr ON public.lobbyist_identity(capital_city_repr_id);
CREATE INDEX IF NOT EXISTS idx_identity_address ON public.lobbyist_identity(address_id);
CREATE INDEX IF NOT EXISTS idx_identity_contact ON public.lobbyist_identity(contact_id);
CREATE INDEX IF NOT EXISTS idx_identity_legal_form_label ON public.lobbyist_identity(legal_form_label_id);
CREATE INDEX IF NOT EXISTS idx_identity_legal_form_type ON public.lobbyist_identity(legal_form_type_label_id);
CREATE INDEX IF NOT EXISTS idx_capital_city_repr_address ON public.capital_city_representation(address_id);
CREATE INDEX IF NOT EXISTS idx_capital_city_repr_contact ON public.capital_city_representation(contact_id);
CREATE INDEX IF NOT EXISTS idx_entrusted_person_identity ON public.entrusted_person(identity_id);
CREATE INDEX IF NOT EXISTS idx_entrusted_person_recent_gov ON public.entrusted_person(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_legal_rep_identity ON public.legal_representative(identity_id);
CREATE INDEX IF NOT EXISTS idx_legal_rep_recent_gov ON public.legal_representative(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_legal_rep_contact ON public.legal_representative(contact_id);
CREATE INDEX IF NOT EXISTS idx_named_employee_identity ON public.named_employee(identity_id);
CREATE INDEX IF NOT EXISTS idx_members_count_identity ON public.members_count(identity_id);
CREATE INDEX IF NOT EXISTS idx_membership_identity ON public.membership(identity_id);

-- Government function taxonomy / lookups
CREATE INDEX IF NOT EXISTS idx_recent_gov_fn_type ON public.recent_government_function(type_label_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_ended_date ON public.recent_government_function(ended, end_year_month DESC);
CREATE INDEX IF NOT EXISTS idx_recent_gov_house_fn ON public.recent_gov_house_reps(recent_gov_fn_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_house_label ON public.recent_gov_house_reps(function_label_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_fed_fn ON public.recent_gov_federal_gov(recent_gov_fn_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_fed_label ON public.recent_gov_federal_gov(function_label_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_fed_dept ON public.recent_gov_federal_gov(department_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_admin_fn ON public.recent_gov_federal_admin(recent_gov_fn_id);

-- Activities & interests
CREATE INDEX IF NOT EXISTS idx_activities_entry ON public.activities_interests(entry_id);
CREATE INDEX IF NOT EXISTS idx_activities_label ON public.activities_interests(activity_label_id);
CREATE INDEX IF NOT EXISTS idx_activity_ex_type_activities ON public.activity_exercising_type(activities_id);
CREATE INDEX IF NOT EXISTS idx_activity_ex_type_label ON public.activity_exercising_type(label_id);
CREATE INDEX IF NOT EXISTS idx_field_of_interest_activities ON public.field_of_interest(activities_id);
CREATE INDEX IF NOT EXISTS idx_field_of_interest_label ON public.field_of_interest(label_id);
CREATE INDEX IF NOT EXISTS idx_legislative_project_activities ON public.legislative_project(activities_id);

-- Clients
CREATE INDEX IF NOT EXISTS idx_client_identity_entry ON public.client_identity(entry_id);
CREATE INDEX IF NOT EXISTS idx_client_org_ci ON public.client_org(client_identity_id);
CREATE INDEX IF NOT EXISTS idx_client_org_address ON public.client_org(address_id);
CREATE INDEX IF NOT EXISTS idx_client_org_contact ON public.client_org(contact_id);
CREATE INDEX IF NOT EXISTS idx_client_org_lr_org ON public.client_org_legal_rep(client_org_id);
CREATE INDEX IF NOT EXISTS idx_client_person_ci ON public.client_person(client_identity_id);

-- Employees & membership
CREATE INDEX IF NOT EXISTS idx_employees_involved_entry ON public.employees_involved(entry_id);
CREATE INDEX IF NOT EXISTS idx_membership_fees_entry ON public.membership_fees(entry_id);
CREATE INDEX IF NOT EXISTS idx_individual_contributor_fees ON public.individual_contributor(fees_id);

-- Finance / allowances / donations / funding
CREATE INDEX IF NOT EXISTS idx_financial_expenses_entry ON public.financial_expenses(entry_id);
CREATE INDEX IF NOT EXISTS idx_financial_expenses_year_amount ON public.financial_expenses(fiscal_year_start_ym, expenses_to_eur);
CREATE INDEX IF NOT EXISTS idx_public_allowance_country ON public.public_allowance_item(country_id);
CREATE INDEX IF NOT EXISTS idx_public_allowances_entry ON public.public_allowances(entry_id);
CREATE INDEX IF NOT EXISTS idx_public_allowance_item_parent ON public.public_allowance_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_public_allowance_item_type ON public.public_allowance_item(type_label_id);
CREATE INDEX IF NOT EXISTS idx_main_funding_sources_entry ON public.main_funding_sources(entry_id);
CREATE INDEX IF NOT EXISTS idx_main_funding_source_item_parent ON public.main_funding_source_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_donators_entry ON public.donators(entry_id);
CREATE INDEX IF NOT EXISTS idx_donator_item_parent ON public.donator_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_annual_reports_entry ON public.annual_reports(entry_id);

-- Regulatory projects
CREATE INDEX IF NOT EXISTS idx_regulatory_projects_entry ON public.regulatory_projects(entry_id);
CREATE INDEX IF NOT EXISTS idx_regproj_item_parent ON public.regulatory_project_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_reg_project_printed_matter_proj ON public.reg_project_printed_matter(project_item_id);
CREATE INDEX IF NOT EXISTS idx_reg_project_printed_matter_ministry ON public.reg_project_printed_matter_ministry(printed_matter_id);
CREATE INDEX IF NOT EXISTS idx_reg_project_printed_matter_ministry_id ON public.reg_project_printed_matter_ministry(ministry_id);
CREATE INDEX IF NOT EXISTS idx_migrated_draft_bill_pmatter ON public.migrated_draft_bill(printed_matter_id);
CREATE INDEX IF NOT EXISTS idx_migrated_draft_bill_ministry ON public.migrated_draft_bill_ministry(migrated_db_id);
CREATE INDEX IF NOT EXISTS idx_migrated_draft_bill_ministry_id ON public.migrated_draft_bill_ministry(ministry_id);
CREATE INDEX IF NOT EXISTS idx_draft_bill_project_item ON public.draft_bill(project_item_id);
CREATE INDEX IF NOT EXISTS idx_draft_bill_ministry_bill ON public.draft_bill_ministry(draft_bill_id);
CREATE INDEX IF NOT EXISTS idx_draft_bill_ministry_id ON public.draft_bill_ministry(ministry_id);
CREATE INDEX IF NOT EXISTS idx_reg_proj_affected_law_proj ON public.reg_project_affected_law(project_item_id);
CREATE INDEX IF NOT EXISTS idx_reg_proj_field_of_interest_proj ON public.reg_project_field_of_interest(project_item_id);
CREATE INDEX IF NOT EXISTS idx_reg_proj_field_of_interest_label ON public.reg_project_field_of_interest(label_id);

-- Statements
CREATE INDEX IF NOT EXISTS idx_statements_entry ON public.statements(entry_id);
CREATE INDEX IF NOT EXISTS idx_statement_item_parent ON public.statement_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_group_item ON public.statement_recipient_group(statement_item_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_parliament_group ON public.statement_recipient_parliament(group_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_parliament_label ON public.statement_recipient_parliament(label_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_federal_group ON public.statement_recipient_federal_gov(group_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_federal_dept ON public.statement_recipient_federal_gov(department_id);

-- Contracts
CREATE INDEX IF NOT EXISTS idx_contracts_entry ON public.contracts(entry_id);
CREATE INDEX IF NOT EXISTS idx_contract_item_parent ON public.contract_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_contract_contractors_item ON public.contract_contractors(contract_item_id);
CREATE INDEX IF NOT EXISTS idx_contract_field_of_interest_item ON public.contract_field_of_interest(contract_item_id);
CREATE INDEX IF NOT EXISTS idx_contract_field_of_interest_label ON public.contract_field_of_interest(label_id);
CREATE INDEX IF NOT EXISTS idx_contract_reg_project_ref_item ON public.contract_reg_project_ref(contract_item_id);
CREATE INDEX IF NOT EXISTS idx_contract_clients_item ON public.contract_clients(contract_item_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_clients ON public.contract_client_org(clients_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_address ON public.contract_client_org(address_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_contact ON public.contract_client_org(contact_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_lr_org ON public.contract_client_org_legal_rep(client_org_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_fr_org ON public.contract_client_org_financial_resources(client_org_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_person_clients ON public.contract_client_person(clients_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_person_fr_person ON public.contract_client_person_financial_resources(client_person_id);
CREATE INDEX IF NOT EXISTS idx_contract_entrusted_person_contractors ON public.contractor_entrusted_person(contractors_id);
CREATE INDEX IF NOT EXISTS idx_contract_entrusted_person_recent_gov ON public.contractor_entrusted_person(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_contractors ON public.contractor_org(contractors_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_address ON public.contractor_org(address_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_contact ON public.contractor_org(contact_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_capital_address ON public.contractor_org(capital_city_repr_address_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_capital_contact ON public.contractor_org(capital_city_repr_contact_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_lr_org ON public.contractor_org_legal_rep(contractor_org_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_lr_recent_gov ON public.contractor_org_legal_rep(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_assigned_person_contractors ON public.assigned_person(contractors_id);
CREATE INDEX IF NOT EXISTS idx_assigned_person_recent_gov ON public.assigned_person(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_contract_person_contractors ON public.contractor_person(contractors_id);
CREATE INDEX IF NOT EXISTS idx_contract_person_recent_gov ON public.contractor_person(recent_gov_function_id);

-- Code of conduct
CREATE INDEX IF NOT EXISTS idx_code_of_conduct_entry ON public.code_of_conduct(entry_id);

-- 2) Partial / text search
CREATE INDEX IF NOT EXISTS idx_active_lobbyists_only
    ON public.account_details (active_lobbyist)
    WHERE active_lobbyist = true;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_trgm_lobbyist_name
    ON public.lobbyist_identity USING gin (name_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_trgm_client_name
    ON public.client_org USING gin (name gin_trgm_ops);

-- 3) Flattened views for dashboards (non-materialized)
CREATE OR REPLACE VIEW public.vw_entry_core AS
SELECT
  re.id              AS entry_id,
  re.register_number,
  li.name_text,
  li.identity,
  li.legal_form_text,
  a.city,
  a.country_id
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id
LEFT JOIN public.address a ON li.address_id = a.id;

CREATE OR REPLACE VIEW public.vw_entry_topics AS
SELECT
  re.id AS entry_id,
  li.name_text,
  cl.de AS field_label,
  cl.code AS field_code
FROM public.register_entry re
JOIN public.activities_interests ai ON re.id = ai.entry_id
JOIN public.field_of_interest foi ON ai.id = foi.activities_id
LEFT JOIN public.code_label cl ON foi.label_id = cl.id;

CREATE OR REPLACE VIEW public.vw_entry_financials AS
SELECT
  re.id AS entry_id,
  re.register_number,
  li.name_text,
  a.city,
  fe.fiscal_year_start_ym,
  fe.fiscal_year_end_ym,
  fe.expenses_from_eur,
  fe.expenses_to_eur,
  fe.refuse_info,
  fe.refuse_reason
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id
LEFT JOIN public.address a ON li.address_id = a.id
LEFT JOIN public.financial_expenses fe ON re.id = fe.entry_id;

CREATE OR REPLACE VIEW public.vw_entry_public_allowances AS
SELECT
  re.id AS entry_id,
  li.name_text,
  pa.amount_from_eur,
  pa.amount_to_eur,
  pa.description,
  pa.location,
  cl.de AS type_label,
  a.city,
  a.country_id
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id
JOIN public.public_allowances pas ON re.id = pas.entry_id
JOIN public.public_allowance_item pa ON pas.id = pa.parent_id
LEFT JOIN public.code_label cl ON pa.type_label_id = cl.id
LEFT JOIN public.address a ON li.address_id = a.id;

CREATE OR REPLACE VIEW public.vw_entry_donations AS
SELECT
  re.id AS entry_id,
  li.name_text,
  di.name AS donor_name,
  di.amount_from_eur,
  di.amount_to_eur,
  di.description,
  a.city
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id
JOIN public.donators d ON re.id = d.entry_id
JOIN public.donator_item di ON d.id = di.parent_id
LEFT JOIN public.address a ON li.address_id = a.id;

CREATE OR REPLACE VIEW public.vw_entry_contracts_org AS
SELECT
  re.id AS entry_id,
  li.name_text,
  ci.id AS contract_item_id,
  ci.description,
  co.name AS contractor_name,
  a.city
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id
JOIN public.contracts c ON re.id = c.entry_id
JOIN public.contract_item ci ON c.id = ci.parent_id
JOIN public.contract_contractors cc ON ci.id = cc.contract_item_id
JOIN public.contractor_org co ON cc.id = co.contractors_id
LEFT JOIN public.address a ON li.address_id = a.id;

CREATE OR REPLACE VIEW public.vw_statements_flat AS
SELECT
  re.id AS entry_id,
  li.name_text,
  si.id AS statement_item_id,
  si.regulatory_project_title,
  si.sending_date,
  si.pdf_url,
  si.text_body
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id
JOIN public.statements s ON re.id = s.entry_id
JOIN public.statement_item si ON s.id = si.parent_id;

CREATE OR REPLACE VIEW public.vw_city_finance_summary AS
SELECT
  a.city,
  COUNT(DISTINCT re.id) AS org_count,
  SUM(fe.expenses_to_eur) AS total_expenses
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id
LEFT JOIN public.address a ON li.address_id = a.id
LEFT JOIN public.financial_expenses fe ON re.id = fe.entry_id
GROUP BY a.city;

-- 4) Materialized Views (heavier dashboard helpers)
CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_financial_tops AS
SELECT
    cl.de AS field_of_interest,
    COUNT(DISTINCT re.id) AS lobbyist_count,
    SUM(fe.expenses_to_eur) AS total_spend_max,
    AVG(fe.expenses_to_eur) AS avg_spend
FROM public.register_entry re
JOIN public.activities_interests ai ON re.id = ai.entry_id
JOIN public.field_of_interest foi ON ai.id = foi.activities_id
JOIN public.code_label cl ON foi.label_id = cl.id
LEFT JOIN public.financial_expenses fe ON re.id = fe.entry_id
GROUP BY cl.de;
CREATE INDEX IF NOT EXISTS idx_mv_finance_topic ON public.mv_financial_tops(field_of_interest);

CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_revolving_door_network AS
WITH all_gov_people AS (
    SELECT entry_id, last_name, first_name, recent_gov_function_id, 'Lobbyist' AS role
    FROM public.lobbyist_identity
    WHERE recent_gov_function_present = true
    UNION ALL
    SELECT li.entry_id, ep.last_name, ep.first_name, ep.recent_gov_function_id, 'Entrusted Person' AS role
    FROM public.entrusted_person ep
    JOIN public.lobbyist_identity li ON ep.identity_id = li.id
    WHERE ep.recent_gov_function_present = true
    UNION ALL
    SELECT li.entry_id, lr.last_name, lr.first_name, lr.recent_gov_function_id, 'Legal Rep' AS role
    FROM public.legal_representative lr
    JOIN public.lobbyist_identity li ON lr.identity_id = li.id
    WHERE lr.recent_gov_function_id IS NOT NULL
)
SELECT
    re.register_number,
    li.name_text AS organization_name,
    p.last_name,
    p.first_name,
    p.role,
    rgf.end_year_month,
    cl.de AS gov_function_type
FROM all_gov_people p
JOIN public.register_entry re ON p.entry_id = re.id
JOIN public.lobbyist_identity li ON re.id = li.entry_id
JOIN public.recent_government_function rgf ON p.recent_gov_function_id = rgf.id
LEFT JOIN public.code_label cl ON rgf.type_label_id = cl.id;
CREATE INDEX IF NOT EXISTS idx_mv_revolving_org ON public.mv_revolving_door_network(organization_name);
