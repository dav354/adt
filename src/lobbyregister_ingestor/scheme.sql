-- ============================================================
-- Lobbyregister (Bundestag) — FULL 3NF Relational Schema (PostgreSQL)
-- Version: 1.0 (all JSON eliminated; deeply nested structures normalized)
-- Dialect: PostgreSQL 13+
-- Notes:
--  * All arrays become child tables with `ordinal` to preserve order.
--  * Reusable structures (address, contact, code/de/en, country, department,
--    government function) are factored into shared tables and referenced by FKs.
--  * JSON and JSONB are NOT used; everything is typed columns & link tables.
--  * Add indexes to fit your query patterns; core FK indexes provided.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS public;
SET search_path = public;

-- ========================
-- Enumerations / Domain tables
-- ========================

-- JSON path: accountDetails.registerEntryVersions[].legislation, registerEntryDetails.legislation
CREATE TABLE IF NOT EXISTS legislation_type (
  code TEXT PRIMARY KEY
);

INSERT INTO legislation_type (code) VALUES
  ('GL2022'),
  ('GL2024')
ON CONFLICT DO NOTHING;

-- JSON path: lobbyistIdentity.identity
CREATE TABLE IF NOT EXISTS lobbyist_identity_type (
  code TEXT PRIMARY KEY
);

INSERT INTO lobbyist_identity_type (code) VALUES
  ('NATURAL'),
  ('ORGANIZATION')
ON CONFLICT DO NOTHING;

-- JSON path: *.address.type
CREATE TABLE IF NOT EXISTS address_type (
  code TEXT PRIMARY KEY
);

INSERT INTO address_type (code) VALUES
  ('NATIONAL'),
  ('POSTBOX'),
  ('FOREIGN')
ON CONFLICT DO NOTHING;

-- JSON path: activitiesAndInterests.activityOperationType
CREATE TABLE IF NOT EXISTS activity_operation_type (
  code TEXT PRIMARY KEY
);

INSERT INTO activity_operation_type (code) VALUES
  ('SELF_OPERATED'),
  ('MANDATE_OPERATED'),
  ('BOTH')
ON CONFLICT DO NOTHING;

-- ========================
-- Reusable dimensions
-- ========================

-- Code/label triplet used across the schema ({code,de,en})
-- JSON path: e.g. lobbyistIdentity.naturalPersonType / legalFormType / legalForm,
--             activitiesAndInterests.fieldsOfInterest[].code, typesOfExercisingLobbyWork[],
--             recentGovernmentFunction.type, funding/donation enums
CREATE TABLE IF NOT EXISTS code_label (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  domain       TEXT NOT NULL, -- e.g., 'natural_person_type', 'legal_form_type', 'field_of_interest', etc.
  code         TEXT NOT NULL,
  de           TEXT,
  en           TEXT,
  UNIQUE (domain, code)
);

-- Country labels ({code,de,en}); kept separate for clarity and possible ISO mapping
-- JSON path: *.address.country
CREATE TABLE IF NOT EXISTS country_label (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code         TEXT NOT NULL,
  de           TEXT,
  en           TEXT,
  UNIQUE (code)
);

-- Address block
-- JSON path: lobbyistIdentity.address, lobbyistIdentity.capitalCityRepresentation.address,
--            clientOrganizations[].address, contract* addresses, etc.
CREATE TABLE IF NOT EXISTS address (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind                     TEXT REFERENCES address_type(code),
  national_additional1     TEXT,
  national_additional2     TEXT,
  international_additional1 TEXT,
  international_additional2 TEXT,
  street                   TEXT,
  street_number            TEXT,
  zip_code                 TEXT,
  city                     TEXT,
  post_box                 TEXT,
  country_id               BIGINT REFERENCES country_label(id)
);
CREATE INDEX IF NOT EXISTS idx_address_country ON address(country_id);

-- Contact block (phone + arrays of emails / websites)
-- JSON path: lobbyistIdentity.contactDetails, capitalCityRepresentation.contactDetails,
--            clientOrganizations[].contactDetails, legalRepresentatives[].contactDetails, etc.
CREATE TABLE IF NOT EXISTS contact (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  phone_number  TEXT
);

-- JSON path: *.contactDetails.emails[]
CREATE TABLE IF NOT EXISTS contact_email (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contact_id  BIGINT NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,
  email       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contact_email_contact ON contact_email(contact_id);

-- JSON path: *.contactDetails.websites[]
CREATE TABLE IF NOT EXISTS contact_website (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contact_id  BIGINT NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,
  website     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contact_website_contact ON contact_website(contact_id);

-- Department used in federalGovernment and ministries
-- JSON path: recentGovernmentFunction.federalGovernment.department,
--            regulatoryProjects.leadingMinistries[].ministry
CREATE TABLE IF NOT EXISTS department (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  title           TEXT NOT NULL,
  short_title     TEXT,
  url             TEXT,
  election_period INTEGER
);

-- Government function taxonomy
-- JSON path: recentGovernmentFunction.type
CREATE TABLE IF NOT EXISTS gov_function_type (
  id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  label_id BIGINT NOT NULL REFERENCES code_label(id) ON DELETE RESTRICT
);

-- Generic Government Function instance (reused by various persons)
-- JSON path: lobbyistIdentity.recentGovernmentFunction,
--            entrustedPersons[].recentGovernmentFunction,
--            legalRepresentatives[].recentGovernmentFunction,
--            contract contractors with recentGovernmentFunction fields
CREATE TABLE IF NOT EXISTS recent_government_function (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ended              BOOLEAN,
  end_year_month     TEXT, -- pattern YYYY-MM; enforce with CHECK below
  type_label_id      BIGINT NOT NULL REFERENCES code_label(id) ON DELETE RESTRICT
);
ALTER TABLE recent_government_function
  ADD CONSTRAINT chk_recent_gov_end_ym CHECK (end_year_month IS NULL OR end_year_month ~ '^[0-9]{4}-[0-9]{2}$');

-- House of Representatives function attached to a gov function
-- JSON path: *.recentGovernmentFunction.houseOfRepresentatives
CREATE TABLE IF NOT EXISTS recent_gov_house_reps (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recent_gov_fn_id      BIGINT NOT NULL REFERENCES recent_government_function(id) ON DELETE CASCADE,
  function_label_id     BIGINT NOT NULL REFERENCES code_label(id) ON DELETE RESTRICT,
  function_position     TEXT
);

-- Federal Government function attached to a gov function
-- JSON path: *.recentGovernmentFunction.federalGovernment
CREATE TABLE IF NOT EXISTS recent_gov_federal_gov (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recent_gov_fn_id      BIGINT NOT NULL REFERENCES recent_government_function(id) ON DELETE CASCADE,
  function_label_id     BIGINT NOT NULL REFERENCES code_label(id) ON DELETE RESTRICT,
  department_id         BIGINT REFERENCES department(id)
);

-- Federal Administration function attached to a gov function
-- JSON path: *.recentGovernmentFunction.federalAdministration
CREATE TABLE IF NOT EXISTS recent_gov_federal_admin (
  id                                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recent_gov_fn_id                     BIGINT NOT NULL REFERENCES recent_government_function(id) ON DELETE CASCADE,
  supreme_federal_authority            TEXT,
  supreme_federal_authority_short      TEXT,
  supreme_federal_authority_elect_prd  INTEGER,
  function_text                        TEXT
);

-- ========================
-- Top-level Register Entry
-- ========================

-- JSON path: root register entry object (entries from registerentries[].results[] / registerEntry)
CREATE TABLE IF NOT EXISTS register_entry (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  schema_uri       TEXT,
  source           TEXT NOT NULL,
  source_url       TEXT NOT NULL,
  source_date      TIMESTAMPTZ NOT NULL,
  json_doc_url     TEXT NOT NULL,
  register_number  TEXT NOT NULL,
  UNIQUE (register_number)
);

-- ---------- Account details and versions
-- JSON path: accountDetails
CREATE TABLE IF NOT EXISTS account_details (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                    BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  active_lobbyist             BOOLEAN NOT NULL,
  inactive_lobbyist_start     TIMESTAMPTZ,
  first_publication_date      TIMESTAMPTZ NOT NULL,
  last_update_date            TIMESTAMPTZ,
  account_has_codex_violations BOOLEAN NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_account_details_entry ON account_details(entry_id);

-- JSON path: accountDetails.activeDateRanges[]
CREATE TABLE IF NOT EXISTS account_active_range (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id  BIGINT NOT NULL REFERENCES account_details(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,
  from_date   TIMESTAMPTZ NOT NULL,
  until_date  TIMESTAMPTZ
);

-- JSON path: accountDetails.inactiveDateRanges[]
CREATE TABLE IF NOT EXISTS account_inactive_range (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id  BIGINT NOT NULL REFERENCES account_details(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,
  from_date   TIMESTAMPTZ NOT NULL,
  until_date  TIMESTAMPTZ
);

-- JSON path: accountDetails.registerEntryVersions[]
CREATE TABLE IF NOT EXISTS account_register_entry_version (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id              BIGINT NOT NULL REFERENCES account_details(id) ON DELETE CASCADE,
  ordinal                 INT NOT NULL,
  register_entry_id_num   BIGINT NOT NULL,
  json_detail_url         TEXT,
  version                 INTEGER NOT NULL,
  legislation             TEXT NOT NULL REFERENCES legislation_type(code),
  valid_from_date         TIMESTAMPTZ NOT NULL,
  valid_until_date        TIMESTAMPTZ,
  active_until_date       TIMESTAMPTZ,
  version_active_lobbyist BOOLEAN NOT NULL
);

-- JSON path: accountDetails.codexViolations[]
CREATE TABLE IF NOT EXISTS codex_violation (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id  BIGINT NOT NULL REFERENCES account_details(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,
  name        TEXT NOT NULL
);

-- ---------- Register entry details
-- JSON path: registerEntryDetails
CREATE TABLE IF NOT EXISTS register_entry_details (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id            BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  register_entry_id_num BIGINT NOT NULL,
  legislation         TEXT NOT NULL REFERENCES legislation_type(code),
  version             INTEGER NOT NULL,
  details_page_url    TEXT,
  pdf_url             TEXT,
  valid_from_date     TIMESTAMPTZ NOT NULL,
  valid_until_date    TIMESTAMPTZ,
  refused_anything    BOOLEAN
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_entry_details ON register_entry_details(entry_id, legislation, version);

-- JSON path: registerEntryDetails.annualUpdate
CREATE TABLE IF NOT EXISTS register_entry_annual_update (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  details_id         BIGINT NOT NULL REFERENCES register_entry_details(id) ON DELETE CASCADE,
  update_missing     BOOLEAN,
  last_annual_update TIMESTAMPTZ
);

-- JSON path: registerEntryDetails.fiscalYearUpdate
CREATE TABLE IF NOT EXISTS register_entry_fiscal_year_update (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  details_id                  BIGINT NOT NULL REFERENCES register_entry_details(id) ON DELETE CASCADE,
  update_missing              BOOLEAN,
  last_fiscal_year_update     TIMESTAMPTZ
);

-- ========================
-- Lobbyist Identity (person or organization)
-- ========================

-- JSON path: lobbyistIdentity
CREATE TABLE IF NOT EXISTS lobbyist_identity (
  id                            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                      BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  identity                      TEXT REFERENCES lobbyist_identity_type(code),
  natural_person_type_label_id  BIGINT REFERENCES code_label(id),
  academic_degree_before        TEXT,
  academic_degree_after         TEXT,
  last_name                     TEXT,
  first_name                    TEXT,
  common_first_name             TEXT,
  artist_name                   TEXT,
  company_name                  TEXT,
  recent_gov_function_present   BOOLEAN,
  recent_gov_function_id        BIGINT REFERENCES recent_government_function(id),
  address_id                    BIGINT REFERENCES address(id),
  contact_id                    BIGINT REFERENCES contact(id),
  legal_form_type_label_id      BIGINT REFERENCES code_label(id),
  legal_form_label_id           BIGINT REFERENCES code_label(id),
  legal_form_text               TEXT,
  capital_city_repr_id          BIGINT, -- references capital_city_representation(id) below
  entrusted_persons_present     BOOLEAN,
  name_text                     TEXT,
  members_present               BOOLEAN,
  memberships_present           BOOLEAN
);
CREATE INDEX IF NOT EXISTS idx_identity_entry ON lobbyist_identity(entry_id);

-- Capital city representation (Berlin) wrapper
-- JSON path: lobbyistIdentity.capitalCityRepresentation
CREATE TABLE IF NOT EXISTS capital_city_representation (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  address_id    BIGINT REFERENCES address(id),
  contact_id    BIGINT REFERENCES contact(id)
);
ALTER TABLE lobbyist_identity
  ADD CONSTRAINT fk_identity_ccr FOREIGN KEY (capital_city_repr_id) REFERENCES capital_city_representation(id) ON DELETE SET NULL;

-- Entrusted persons
-- JSON path: lobbyistIdentity.entrustedPersons[]
CREATE TABLE IF NOT EXISTS entrusted_person (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  identity_id                 BIGINT NOT NULL REFERENCES lobbyist_identity(id) ON DELETE CASCADE,
  ordinal                     INT NOT NULL,
  academic_degree_before      TEXT,
  academic_degree_after       TEXT,
  last_name                   TEXT,
  first_name                  TEXT,
  artist_name                 TEXT,
  recent_gov_function_present BOOLEAN,
  recent_gov_function_id      BIGINT REFERENCES recent_government_function(id)
);

-- Legal representatives
-- JSON path: lobbyistIdentity.legalRepresentatives[]
CREATE TABLE IF NOT EXISTS legal_representative (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  identity_id                 BIGINT NOT NULL REFERENCES lobbyist_identity(id) ON DELETE CASCADE,
  ordinal                     INT NOT NULL,
  academic_degree_before      TEXT,
  academic_degree_after       TEXT,
  last_name                   TEXT,
  first_name                  TEXT,
  common_first_name           TEXT,
  artist_name                 TEXT,
  function_text               TEXT,
  recent_gov_function_id      BIGINT REFERENCES recent_government_function(id),
  contact_id                  BIGINT REFERENCES contact(id)
);

-- Named employees
-- JSON path: lobbyistIdentity.namedEmployees[]
CREATE TABLE IF NOT EXISTS named_employee (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  identity_id        BIGINT NOT NULL REFERENCES lobbyist_identity(id) ON DELETE CASCADE,
  ordinal            INT NOT NULL,
  academic_degree_before TEXT,
  academic_degree_after  TEXT,
  last_name          TEXT,
  common_first_name  TEXT
);

-- Members count
-- JSON path: lobbyistIdentity.membersCount
CREATE TABLE IF NOT EXISTS members_count (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  identity_id        BIGINT NOT NULL REFERENCES lobbyist_identity(id) ON DELETE CASCADE,
  natural_persons    INTEGER,
  organizations      INTEGER,
  total_count        INTEGER,
  date_count         DATE
);

-- Memberships (strings)
-- JSON path: lobbyistIdentity.memberships[]
CREATE TABLE IF NOT EXISTS membership (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  identity_id   BIGINT NOT NULL REFERENCES lobbyist_identity(id) ON DELETE CASCADE,
  ordinal       INT NOT NULL,
  membership    TEXT NOT NULL
);

-- ========================
-- Activities & Interests
-- ========================

-- JSON path: activitiesAndInterests
CREATE TABLE IF NOT EXISTS activities_interests (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                 BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  activity_label_id        BIGINT REFERENCES code_label(id),
  activity_text            TEXT,
  activity_legal_basis     TEXT,
  activity_operation_type  TEXT REFERENCES activity_operation_type(code),
  activity_description     TEXT
);
CREATE INDEX IF NOT EXISTS idx_activities_entry ON activities_interests(entry_id);

-- JSON path: activitiesAndInterests.typesOfExercisingLobbyWork[]
CREATE TABLE IF NOT EXISTS activity_exercising_type (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  activities_id    BIGINT NOT NULL REFERENCES activities_interests(id) ON DELETE CASCADE,
  ordinal          INT NOT NULL,
  label_id         BIGINT NOT NULL REFERENCES code_label(id)
);

-- JSON path: activitiesAndInterests.fieldsOfInterest[]
CREATE TABLE IF NOT EXISTS field_of_interest (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  activities_id            BIGINT NOT NULL REFERENCES activities_interests(id) ON DELETE CASCADE,
  ordinal                  INT NOT NULL,
  label_id                 BIGINT REFERENCES code_label(id),
  field_of_interest_text   TEXT
);

-- JSON path: activitiesAndInterests.legislativeProjects[]
CREATE TABLE IF NOT EXISTS legislative_project (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  activities_id      BIGINT NOT NULL REFERENCES activities_interests(id) ON DELETE CASCADE,
  ordinal            INT NOT NULL,
  name               TEXT,
  printing_number    TEXT,
  document_title     TEXT,
  document_url       TEXT
);

-- ========================
-- Client Identity (organizations & persons)
-- ========================

-- JSON path: clientIdentity
CREATE TABLE IF NOT EXISTS client_identity (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id         BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  clients_present  BOOLEAN NOT NULL,
  clients_count    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_client_identity_entry ON client_identity(entry_id);

-- JSON path: clientIdentity.clientOrganizations[]
CREATE TABLE IF NOT EXISTS client_org (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_identity_id        BIGINT NOT NULL REFERENCES client_identity(id) ON DELETE CASCADE,
  ordinal                   INT NOT NULL,
  reference_name            TEXT,
  reference_details_url     TEXT,
  name                      TEXT,
  legal_form_type_label_id  BIGINT REFERENCES code_label(id),
  legal_form_label_id       BIGINT REFERENCES code_label(id),
  legal_form_text           TEXT,
  address_id                BIGINT REFERENCES address(id),
  contact_id                BIGINT REFERENCES contact(id)
);
CREATE INDEX IF NOT EXISTS idx_client_org_ci ON client_org(client_identity_id);

-- JSON path: clientIdentity.clientOrganizations[].legalRepresentatives[]
CREATE TABLE IF NOT EXISTS client_org_legal_rep (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_org_id      BIGINT NOT NULL REFERENCES client_org(id) ON DELETE CASCADE,
  ordinal            INT NOT NULL,
  academic_degree_before TEXT,
  academic_degree_after  TEXT,
  common_first_name  TEXT,
  last_name          TEXT,
  function_text      TEXT,
  contact_id         BIGINT REFERENCES contact(id)
);

-- JSON path: clientIdentity.clientPersons[]
CREATE TABLE IF NOT EXISTS client_person (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_identity_id        BIGINT NOT NULL REFERENCES client_identity(id) ON DELETE CASCADE,
  ordinal                   INT NOT NULL,
  reference_name            TEXT,
  reference_details_url     TEXT,
  academic_degree_before    TEXT,
  academic_degree_after     TEXT,
  last_name                 TEXT,
  common_first_name         TEXT
);

-- ========================
-- Employees involved in lobbying
-- ========================

-- JSON path: employeesInvolvedInLobbying
CREATE TABLE IF NOT EXISTS employees_involved (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  related_year_finished   BOOLEAN,
  related_year_start      DATE,
  related_year_end        DATE,
  employees_from          INTEGER,
  employees_to            INTEGER,
  employee_fte            NUMERIC
);

-- ========================
-- Financial Expenses
-- ========================

-- JSON path: financialExpenses
CREATE TABLE IF NOT EXISTS financial_expenses (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  refuse_info             BOOLEAN,
  refuse_reason           TEXT,
  related_year_finished   BOOLEAN,
  related_year_start      DATE,
  related_year_end        DATE,
  fiscal_year_completed   BOOLEAN,
  fiscal_year_start_ym    TEXT,
  fiscal_year_end_ym      TEXT,
  expenses_from_eur       BIGINT,
  expenses_to_eur         BIGINT
);
ALTER TABLE financial_expenses
  ADD CONSTRAINT chk_finexp_start_ym CHECK (fiscal_year_start_ym IS NULL OR fiscal_year_start_ym ~ '^[0-9]{4}-[0-9]{2}$');
ALTER TABLE financial_expenses
  ADD CONSTRAINT chk_finexp_end_ym CHECK (fiscal_year_end_ym IS NULL OR fiscal_year_end_ym ~ '^[0-9]{4}-[0-9]{2}$');

-- ========================
-- Main Funding Sources
-- ========================

-- JSON path: mainFundingSources
CREATE TABLE IF NOT EXISTS main_funding_sources (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  related_year_finished   BOOLEAN,
  related_year_start      DATE,
  related_year_end        DATE
);

-- JSON path: mainFundingSources.mainFundingSources[]
CREATE TABLE IF NOT EXISTS main_funding_source_item (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id   BIGINT NOT NULL REFERENCES main_funding_sources(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,
  label_id    BIGINT REFERENCES code_label(id)
);

-- ========================
-- Public Allowances
-- ========================

-- JSON path: publicAllowances
CREATE TABLE IF NOT EXISTS public_allowances (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  refuse_info             BOOLEAN,
  refuse_reason           TEXT,
  allowances_present      BOOLEAN,
  related_year_finished   BOOLEAN,
  related_year_start      DATE,
  related_year_end        DATE,
  fiscal_year_completed   BOOLEAN,
  fiscal_year_start_ym    TEXT,
  fiscal_year_end_ym      TEXT
);
ALTER TABLE public_allowances
  ADD CONSTRAINT chk_puball_start_ym CHECK (fiscal_year_start_ym IS NULL OR fiscal_year_start_ym ~ '^[0-9]{4}-[0-9]{2}$');
ALTER TABLE public_allowances
  ADD CONSTRAINT chk_puball_end_ym CHECK (fiscal_year_end_ym IS NULL OR fiscal_year_end_ym ~ '^[0-9]{4}-[0-9]{2}$');

-- JSON path: publicAllowances.publicAllowances[]
CREATE TABLE IF NOT EXISTS public_allowance_item (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id         BIGINT NOT NULL REFERENCES public_allowances(id) ON DELETE CASCADE,
  ordinal           INT NOT NULL,
  name              TEXT,
  type_label_id     BIGINT REFERENCES code_label(id),
  country_id        BIGINT REFERENCES country_label(id),
  location          TEXT,
  amount_from_eur   BIGINT,
  amount_to_eur     BIGINT,
  description       TEXT
);

-- ========================
-- Donators (Donations)
-- ========================

-- JSON path: donators
CREATE TABLE IF NOT EXISTS donators (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  refuse_info             BOOLEAN,
  refuse_reason           TEXT,
  info_present            BOOLEAN,
  related_year_finished   BOOLEAN,
  related_year_start      DATE,
  related_year_end        DATE,
  fiscal_year_completed   BOOLEAN,
  fiscal_year_start_ym    TEXT,
  fiscal_year_end_ym      TEXT,
  total_from_eur          BIGINT,
  total_to_eur            BIGINT
);
ALTER TABLE donators
  ADD CONSTRAINT chk_don_start_ym CHECK (fiscal_year_start_ym IS NULL OR fiscal_year_start_ym ~ '^[0-9]{4}-[0-9]{2}$');
ALTER TABLE donators
  ADD CONSTRAINT chk_don_end_ym CHECK (fiscal_year_end_ym IS NULL OR fiscal_year_end_ym ~ '^[0-9]{4}-[0-9]{2}$');

-- JSON path: donators.donators[]
CREATE TABLE IF NOT EXISTS donator_item (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id         BIGINT NOT NULL REFERENCES donators(id) ON DELETE CASCADE,
  ordinal           INT NOT NULL,
  name              TEXT,
  amount_from_eur   BIGINT,
  amount_to_eur     BIGINT,
  description       TEXT
);

-- ========================
-- Membership Fees
-- ========================

-- JSON path: membershipFees
CREATE TABLE IF NOT EXISTS membership_fees (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                    BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  related_year_finished       BOOLEAN NOT NULL,
  related_year_start          DATE,
  related_year_end            DATE,
  total_from_eur              BIGINT,
  total_to_eur                BIGINT,
  individual_contributors_present BOOLEAN
);

-- JSON path: membershipFees.individualContributors[]
CREATE TABLE IF NOT EXISTS individual_contributor (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fees_id     BIGINT NOT NULL REFERENCES membership_fees(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,
  name        TEXT
);

-- ========================
-- Annual Reports
-- ========================

-- JSON path: annualReports
CREATE TABLE IF NOT EXISTS annual_reports (
  id                              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id                        BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  disclosure_requirements_exist   BOOLEAN,
  refuse_annual_fin_stmt          BOOLEAN,
  refuse_annual_fin_stmt_reason   TEXT,
  annual_report_exists            BOOLEAN,
  annual_report_last_fy_exists    BOOLEAN,
  annual_report_prev_last_fy_exists BOOLEAN,
  finished_fy_exists              BOOLEAN,
  last_fy_start                   DATE,
  last_fy_end                     DATE,
  prev_last_fy_start              DATE,
  prev_last_fy_end                DATE,
  annual_report_pdf_url           TEXT,
  missing_annual_report_reason    TEXT,
  report_was_published_elsewhere  BOOLEAN,
  location_of_report_publication  TEXT
);

-- ========================
-- Regulatory Projects
-- ========================

-- JSON path: regulatoryProjects
CREATE TABLE IF NOT EXISTS regulatory_projects (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id            BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  projects_present    BOOLEAN,
  projects_count      INTEGER
);

-- JSON path: regulatoryProjects.regulatoryProjects[]
CREATE TABLE IF NOT EXISTS regulatory_project_item (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id               BIGINT NOT NULL REFERENCES regulatory_projects(id) ON DELETE CASCADE,
  ordinal                 INT NOT NULL,
  regulatory_project_number TEXT,
  title                   TEXT,
  printed_matters_present BOOLEAN,
  draft_bill_present      BOOLEAN,
  description             TEXT
);

-- Printed matters under regulatory project
-- JSON path: regulatoryProjects.regulatoryProjects[].printedMatters[]
CREATE TABLE IF NOT EXISTS reg_project_printed_matter (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_item_id     BIGINT NOT NULL REFERENCES regulatory_project_item(id) ON DELETE CASCADE,
  ordinal             INT NOT NULL,
  title               TEXT,
  printing_number     TEXT,
  issuer              TEXT,
  document_url        TEXT,
  project_url         TEXT
);

-- Leading ministries (reused in multiple places)
-- JSON path: *.leadingMinistries[] and federalGovernment.department
CREATE TABLE IF NOT EXISTS leading_ministry (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  title           TEXT,
  short_title     TEXT,
  url             TEXT,
  election_period INTEGER
);

-- Link tables for ministries
-- JSON path: regulatoryProjects.regulatoryProjects[].printedMatters[].leadingMinistries[]
CREATE TABLE IF NOT EXISTS reg_project_printed_matter_ministry (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  printed_matter_id     BIGINT NOT NULL REFERENCES reg_project_printed_matter(id) ON DELETE CASCADE,
  ordinal               INT NOT NULL,
  ministry_id           BIGINT NOT NULL REFERENCES leading_ministry(id)
);

-- Migrated draft bill under printed matter
-- JSON path: regulatoryProjects.regulatoryProjects[].printedMatters[].migratedDraftBill
CREATE TABLE IF NOT EXISTS migrated_draft_bill (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  printed_matter_id   BIGINT NOT NULL REFERENCES reg_project_printed_matter(id) ON DELETE CASCADE,
  title               TEXT,
  publication_date    DATE
);

-- JSON path: regulatoryProjects.regulatoryProjects[].printedMatters[].migratedDraftBill.leadingMinistries[]
CREATE TABLE IF NOT EXISTS migrated_draft_bill_ministry (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  migrated_db_id    BIGINT NOT NULL REFERENCES migrated_draft_bill(id) ON DELETE CASCADE,
  ordinal           INT NOT NULL,
  ministry_id       BIGINT NOT NULL REFERENCES leading_ministry(id),
  draft_bill_document_url TEXT,
  draft_bill_project_url  TEXT
);

-- Draft bill (direct under project)
-- JSON path: regulatoryProjects.regulatoryProjects[].draftBill
CREATE TABLE IF NOT EXISTS draft_bill (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_item_id     BIGINT NOT NULL REFERENCES regulatory_project_item(id) ON DELETE CASCADE,
  title               TEXT,
  publication_date    DATE,
  custom_title        TEXT,
  custom_date         DATE
);

-- JSON path: regulatoryProjects.regulatoryProjects[].draftBill.leadingMinistries[]
CREATE TABLE IF NOT EXISTS draft_bill_ministry (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  draft_bill_id     BIGINT NOT NULL REFERENCES draft_bill(id) ON DELETE CASCADE,
  ordinal           INT NOT NULL,
  ministry_id       BIGINT NOT NULL REFERENCES leading_ministry(id),
  draft_bill_document_url TEXT,
  draft_bill_project_url  TEXT
);

-- Affected laws under project
-- JSON path: regulatoryProjects.regulatoryProjects[].affectedLaws[]
CREATE TABLE IF NOT EXISTS reg_project_affected_law (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_item_id BIGINT NOT NULL REFERENCES regulatory_project_item(id) ON DELETE CASCADE,
  ordinal         INT NOT NULL,
  title           TEXT,
  short_title     TEXT,
  url             TEXT
);

-- Fields of interest under project item
-- JSON path: regulatoryProjects.regulatoryProjects[].fieldsOfInterest[]
CREATE TABLE IF NOT EXISTS reg_project_field_of_interest (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_item_id BIGINT NOT NULL REFERENCES regulatory_project_item(id) ON DELETE CASCADE,
  ordinal         INT NOT NULL,
  label_id        BIGINT REFERENCES code_label(id),
  field_of_interest_text TEXT
);

-- ========================
-- Statements
-- ========================

-- JSON path: statements
CREATE TABLE IF NOT EXISTS statements (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id           BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  statements_present BOOLEAN,
  statements_count   INTEGER
);

-- JSON path: statements.statements[]
CREATE TABLE IF NOT EXISTS statement_item (
  id                           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id                    BIGINT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
  ordinal                      INT NOT NULL,
  statement_number             TEXT,
  regulatory_project_number    TEXT,
  regulatory_project_title     TEXT,
  pdf_url                      TEXT,
  pdf_page_count               INTEGER,
  copyright_acknowledgement    TEXT,
  text_body                    TEXT,
  sending_date                 DATE
);

-- Recipients per statement item (group wrapper)
-- JSON path: statements.statements[].recipientGroups[]
CREATE TABLE IF NOT EXISTS statement_recipient_group (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  statement_item_id BIGINT NOT NULL REFERENCES statement_item(id) ON DELETE CASCADE,
  ordinal          INT NOT NULL
);

-- Parliament recipients (labels)
-- JSON path: statements.statements[].recipientGroups[].recipients.parliament[]
CREATE TABLE IF NOT EXISTS statement_recipient_parliament (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  group_id                  BIGINT NOT NULL REFERENCES statement_recipient_group(id) ON DELETE CASCADE,
  ordinal                   INT NOT NULL,
  label_id                  BIGINT NOT NULL REFERENCES code_label(id)
);

-- Federal government recipients (departments)
-- JSON path: statements.statements[].recipientGroups[].recipients.federalGovernment[]
CREATE TABLE IF NOT EXISTS statement_recipient_federal_gov (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  group_id                  BIGINT NOT NULL REFERENCES statement_recipient_group(id) ON DELETE CASCADE,
  ordinal                   INT NOT NULL,
  department_id             BIGINT NOT NULL REFERENCES department(id)
);

-- ========================
-- Contracts
-- ========================

-- JSON path: contracts
CREATE TABLE IF NOT EXISTS contracts (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id           BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  contracts_present  BOOLEAN,
  contracts_count    INTEGER
);

-- JSON path: contracts.contracts[]
CREATE TABLE IF NOT EXISTS contract_item (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id         BIGINT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  ordinal           INT NOT NULL,
  description       TEXT
);

-- Contract fields of interest
-- JSON path: contracts.contracts[].fieldsOfInterest[]
CREATE TABLE IF NOT EXISTS contract_field_of_interest (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contract_item_id BIGINT NOT NULL REFERENCES contract_item(id) ON DELETE CASCADE,
  ordinal         INT NOT NULL,
  label_id        BIGINT REFERENCES code_label(id),
  field_of_interest_text TEXT
);

-- Contract regulatory projects (number+title only)
-- JSON path: contracts.contracts[].regulatoryProjects[]
CREATE TABLE IF NOT EXISTS contract_reg_project_ref (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contract_item_id BIGINT NOT NULL REFERENCES contract_item(id) ON DELETE CASCADE,
  ordinal         INT NOT NULL,
  regulatory_project_number TEXT NOT NULL,
  regulatory_project_title  TEXT NOT NULL
);

-- Contract clients wrapper (orgs + persons)
-- JSON path: contracts.contracts[].clients
CREATE TABLE IF NOT EXISTS contract_clients (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contract_item_id BIGINT NOT NULL REFERENCES contract_item(id) ON DELETE CASCADE
);

-- Contract client organizations (structure mirrors client_org, trimmed to required fields)
-- JSON path: contracts.contracts[].clients.clientOrganizations[]
CREATE TABLE IF NOT EXISTS contract_client_org (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  clients_id                BIGINT NOT NULL REFERENCES contract_clients(id) ON DELETE CASCADE,
  ordinal                   INT NOT NULL,
  reference_name            TEXT,
  reference_details_url     TEXT,
  name                      TEXT,
  legal_form_type_label_id  BIGINT REFERENCES code_label(id),
  legal_form_label_id       BIGINT REFERENCES code_label(id),
  legal_form_text           TEXT,
  address_id                BIGINT REFERENCES address(id),
  contact_id                BIGINT REFERENCES contact(id)
);

-- JSON path: contracts.contracts[].clients.clientOrganizations[].legalRepresentatives[]
CREATE TABLE IF NOT EXISTS contract_client_org_legal_rep (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_org_id      BIGINT NOT NULL REFERENCES contract_client_org(id) ON DELETE CASCADE,
  ordinal            INT NOT NULL,
  academic_degree_before TEXT,
  academic_degree_after  TEXT,
  first_name         TEXT,
  last_name          TEXT,
  artist_name        TEXT,
  function_text      TEXT
);

-- JSON path: contracts.contracts[].clients.clientOrganizations[].financialResourcesReceived
CREATE TABLE IF NOT EXISTS contract_client_org_financial_resources (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_org_id         BIGINT NOT NULL REFERENCES contract_client_org(id) ON DELETE CASCADE,
  last_fiscal_year_finished BOOLEAN,
  last_fiscal_year_start    DATE,
  last_fiscal_year_end      DATE,
  amount_from_eur           BIGINT,
  amount_to_eur             BIGINT
);

-- Contract client persons
-- JSON path: contracts.contracts[].clients.clientPersons[]
CREATE TABLE IF NOT EXISTS contract_client_person (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  clients_id                BIGINT NOT NULL REFERENCES contract_clients(id) ON DELETE CASCADE,
  ordinal                   INT NOT NULL,
  reference_name            TEXT,
  reference_details_url     TEXT,
  academic_degree_before    TEXT,
  academic_degree_after     TEXT,
  last_name                 TEXT,
  first_name                TEXT,
  artist_name               TEXT,
  company_name              TEXT
);

-- JSON path: contracts.contracts[].clients.clientPersons[].financialResourcesReceived
CREATE TABLE IF NOT EXISTS contract_client_person_financial_resources (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_person_id      BIGINT NOT NULL REFERENCES contract_client_person(id) ON DELETE CASCADE,
  last_fiscal_year_finished BOOLEAN,
  last_fiscal_year_start    DATE,
  last_fiscal_year_end      DATE,
  amount_from_eur           BIGINT,
  amount_to_eur             BIGINT
);

-- Contractors wrapper
-- JSON path: contracts.contracts[].contractors
CREATE TABLE IF NOT EXISTS contract_contractors (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contract_item_id          BIGINT NOT NULL REFERENCES contract_item(id) ON DELETE CASCADE,
  lobbying_is_carried_out_by_lobbyist BOOLEAN
);

-- Contractors: entrusted persons performing lobbying
-- JSON path: contracts.contracts[].contractors.entrustedPersons[]
CREATE TABLE IF NOT EXISTS contractor_entrusted_person (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contractors_id              BIGINT NOT NULL REFERENCES contract_contractors(id) ON DELETE CASCADE,
  ordinal                     INT NOT NULL,
  academic_degree_before      TEXT,
  academic_degree_after       TEXT,
  first_name                  TEXT,
  last_name                   TEXT,
  artist_name                 TEXT,
  function_text               TEXT,
  recent_gov_function_present BOOLEAN,
  recent_gov_function_id      BIGINT REFERENCES recent_government_function(id)
);

-- Contractor Organizations
-- JSON path: contracts.contracts[].contractors.contractorOrganizations[]
CREATE TABLE IF NOT EXISTS contractor_org (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contractors_id            BIGINT NOT NULL REFERENCES contract_contractors(id) ON DELETE CASCADE,
  ordinal                   INT NOT NULL,
  reference_name            TEXT,
  reference_details_url     TEXT,
  name                      TEXT,
  legal_form_type_label_id  BIGINT REFERENCES code_label(id),
  legal_form_label_id       BIGINT REFERENCES code_label(id),
  legal_form_text           TEXT,
  address_id                BIGINT REFERENCES address(id),
  contact_id                BIGINT REFERENCES contact(id),
  capital_city_repr_address_id BIGINT REFERENCES address(id),
  capital_city_repr_contact_id BIGINT REFERENCES contact(id)
);

-- JSON path: contracts.contracts[].contractors.contractorOrganizations[].legalRepresentatives[]
CREATE TABLE IF NOT EXISTS contractor_org_legal_rep (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contractor_org_id  BIGINT NOT NULL REFERENCES contractor_org(id) ON DELETE CASCADE,
  ordinal            INT NOT NULL,
  academic_degree_before TEXT,
  academic_degree_after  TEXT,
  first_name         TEXT,
  last_name          TEXT,
  artist_name        TEXT,
  function_text      TEXT,
  recent_gov_function_present BOOLEAN,
  recent_gov_function_id      BIGINT REFERENCES recent_government_function(id)
);

-- Assigned persons (contractors)
-- JSON path: contracts.contracts[].contractors.contractorOrganizations[].assignedPersons[]
CREATE TABLE IF NOT EXISTS assigned_person (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contractors_id              BIGINT NOT NULL REFERENCES contract_contractors(id) ON DELETE CASCADE,
  ordinal                     INT NOT NULL,
  academic_degree_before      TEXT,
  academic_degree_after       TEXT,
  first_name                  TEXT,
  last_name                   TEXT,
  artist_name                 TEXT,
  recent_gov_function_present BOOLEAN,
  recent_gov_function_id      BIGINT REFERENCES recent_government_function(id)
);

-- Contractor Persons (separate list)
-- JSON path: contracts.contracts[].contractors.contractorPersons[]
CREATE TABLE IF NOT EXISTS contractor_person (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contractors_id              BIGINT NOT NULL REFERENCES contract_contractors(id) ON DELETE CASCADE,
  ordinal                     INT NOT NULL,
  reference_name              TEXT,
  reference_details_url       TEXT,
  academic_degree_before      TEXT,
  academic_degree_after       TEXT,
  last_name                   TEXT,
  first_name                  TEXT,
  artist_name                 TEXT,
  company_name                TEXT,
  recent_gov_function_present BOOLEAN,
  recent_gov_function_id      BIGINT REFERENCES recent_government_function(id)
);

-- ========================
-- Code of Conduct
-- ========================

-- JSON path: codeOfConduct
CREATE TABLE IF NOT EXISTS code_of_conduct (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id              BIGINT NOT NULL REFERENCES register_entry(id) ON DELETE CASCADE,
  own_code_of_conduct   BOOLEAN NOT NULL,
  code_of_conduct_pdf_url TEXT
);

-- ========================
-- Indexes for FK acceleration (selected)
-- ========================
CREATE INDEX IF NOT EXISTS idx_recent_gov_fn_type ON recent_government_function(type_label_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_house_fn ON recent_gov_house_reps(recent_gov_fn_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_house_label ON recent_gov_house_reps(function_label_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_fed_fn ON recent_gov_federal_gov(recent_gov_fn_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_fed_label ON recent_gov_federal_gov(function_label_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_fed_dept ON recent_gov_federal_gov(department_id);
CREATE INDEX IF NOT EXISTS idx_recent_gov_admin_fn ON recent_gov_federal_admin(recent_gov_fn_id);

CREATE INDEX IF NOT EXISTS idx_account_active_account ON account_active_range(account_id);
CREATE INDEX IF NOT EXISTS idx_account_inactive_account ON account_inactive_range(account_id);
CREATE INDEX IF NOT EXISTS idx_account_rev_account ON account_register_entry_version(account_id);
CREATE INDEX IF NOT EXISTS idx_codex_violation_account ON codex_violation(account_id);
CREATE INDEX IF NOT EXISTS idx_entry_details_entry ON register_entry_details(entry_id);
CREATE INDEX IF NOT EXISTS idx_entry_annual_details ON register_entry_annual_update(details_id);
CREATE INDEX IF NOT EXISTS idx_entry_fiscal_details ON register_entry_fiscal_year_update(details_id);

CREATE INDEX IF NOT EXISTS idx_identity_recent_gov ON lobbyist_identity(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_identity_capital_city_repr ON lobbyist_identity(capital_city_repr_id);
CREATE INDEX IF NOT EXISTS idx_identity_address ON lobbyist_identity(address_id);
CREATE INDEX IF NOT EXISTS idx_identity_contact ON lobbyist_identity(contact_id);
CREATE INDEX IF NOT EXISTS idx_identity_legal_form_label ON lobbyist_identity(legal_form_label_id);
CREATE INDEX IF NOT EXISTS idx_identity_legal_form_type ON lobbyist_identity(legal_form_type_label_id);
CREATE INDEX IF NOT EXISTS idx_capital_city_repr_address ON capital_city_representation(address_id);
CREATE INDEX IF NOT EXISTS idx_capital_city_repr_contact ON capital_city_representation(contact_id);
CREATE INDEX IF NOT EXISTS idx_entrusted_person_identity ON entrusted_person(identity_id);
CREATE INDEX IF NOT EXISTS idx_entrusted_person_recent_gov ON entrusted_person(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_legal_rep_identity ON legal_representative(identity_id);
CREATE INDEX IF NOT EXISTS idx_legal_rep_recent_gov ON legal_representative(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_legal_rep_contact ON legal_representative(contact_id);
CREATE INDEX IF NOT EXISTS idx_named_employee_identity ON named_employee(identity_id);
CREATE INDEX IF NOT EXISTS idx_members_count_identity ON members_count(identity_id);
CREATE INDEX IF NOT EXISTS idx_membership_identity ON membership(identity_id);

CREATE INDEX IF NOT EXISTS idx_financial_expenses_entry ON financial_expenses(entry_id);
CREATE INDEX IF NOT EXISTS idx_financial_expenses_year_amount ON financial_expenses(fiscal_year_start_ym, expenses_to_eur);
CREATE INDEX IF NOT EXISTS idx_activity_ex_type_activities ON activity_exercising_type(activities_id);
CREATE INDEX IF NOT EXISTS idx_activity_ex_type_label ON activity_exercising_type(label_id);
CREATE INDEX IF NOT EXISTS idx_field_of_interest_activities ON field_of_interest(activities_id);
CREATE INDEX IF NOT EXISTS idx_field_of_interest_label ON field_of_interest(label_id);
CREATE INDEX IF NOT EXISTS idx_legislative_project_activities ON legislative_project(activities_id);

CREATE INDEX IF NOT EXISTS idx_donators_entry ON donators(entry_id);
CREATE INDEX IF NOT EXISTS idx_donator_item_parent ON donator_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_client_org_address ON client_org(address_id);
CREATE INDEX IF NOT EXISTS idx_client_org_contact ON client_org(contact_id);
CREATE INDEX IF NOT EXISTS idx_client_org_lr_org ON client_org_legal_rep(client_org_id);
CREATE INDEX IF NOT EXISTS idx_client_person_ci ON client_person(client_identity_id);
CREATE INDEX IF NOT EXISTS idx_employees_involved_entry ON employees_involved(entry_id);
CREATE INDEX IF NOT EXISTS idx_public_allowance_country ON public_allowance_item(country_id);
CREATE INDEX IF NOT EXISTS idx_public_allowances_entry ON public_allowances(entry_id);
CREATE INDEX IF NOT EXISTS idx_public_allowance_item_parent ON public_allowance_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_public_allowance_item_type ON public_allowance_item(type_label_id);
CREATE INDEX IF NOT EXISTS idx_main_funding_sources_entry ON main_funding_sources(entry_id);
CREATE INDEX IF NOT EXISTS idx_main_funding_source_item_parent ON main_funding_source_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_membership_fees_entry ON membership_fees(entry_id);
CREATE INDEX IF NOT EXISTS idx_individual_contributor_fees ON individual_contributor(fees_id);
CREATE INDEX IF NOT EXISTS idx_annual_reports_entry ON annual_reports(entry_id);

CREATE INDEX IF NOT EXISTS idx_contracts_entry ON contracts(entry_id);
CREATE INDEX IF NOT EXISTS idx_contract_contractors_item ON contract_contractors(contract_item_id);
CREATE INDEX IF NOT EXISTS idx_regproj_item_parent ON regulatory_project_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_regulatory_projects_entry ON regulatory_projects(entry_id);
CREATE INDEX IF NOT EXISTS idx_reg_project_printed_matter_proj ON reg_project_printed_matter(project_item_id);
CREATE INDEX IF NOT EXISTS idx_reg_project_printed_matter_ministry ON reg_project_printed_matter_ministry(printed_matter_id);
CREATE INDEX IF NOT EXISTS idx_reg_project_printed_matter_ministry_id ON reg_project_printed_matter_ministry(ministry_id);
CREATE INDEX IF NOT EXISTS idx_migrated_draft_bill_pmatter ON migrated_draft_bill(printed_matter_id);
CREATE INDEX IF NOT EXISTS idx_migrated_draft_bill_ministry ON migrated_draft_bill_ministry(migrated_db_id);
CREATE INDEX IF NOT EXISTS idx_migrated_draft_bill_ministry_id ON migrated_draft_bill_ministry(ministry_id);
CREATE INDEX IF NOT EXISTS idx_draft_bill_project_item ON draft_bill(project_item_id);
CREATE INDEX IF NOT EXISTS idx_draft_bill_ministry_bill ON draft_bill_ministry(draft_bill_id);
CREATE INDEX IF NOT EXISTS idx_draft_bill_ministry_id ON draft_bill_ministry(ministry_id);
CREATE INDEX IF NOT EXISTS idx_reg_proj_affected_law_proj ON reg_project_affected_law(project_item_id);
CREATE INDEX IF NOT EXISTS idx_reg_proj_field_of_interest_proj ON reg_project_field_of_interest(project_item_id);
CREATE INDEX IF NOT EXISTS idx_reg_proj_field_of_interest_label ON reg_project_field_of_interest(label_id);

CREATE INDEX IF NOT EXISTS idx_statements_entry ON statements(entry_id);
CREATE INDEX IF NOT EXISTS idx_statement_item_parent ON statement_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_contract_item_parent ON contract_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_group_item ON statement_recipient_group(statement_item_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_parliament_group ON statement_recipient_parliament(group_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_parliament_label ON statement_recipient_parliament(label_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_federal_group ON statement_recipient_federal_gov(group_id);
CREATE INDEX IF NOT EXISTS idx_statement_recipient_federal_dept ON statement_recipient_federal_gov(department_id);

CREATE INDEX IF NOT EXISTS idx_contract_field_of_interest_item ON contract_field_of_interest(contract_item_id);
CREATE INDEX IF NOT EXISTS idx_contract_field_of_interest_label ON contract_field_of_interest(label_id);
CREATE INDEX IF NOT EXISTS idx_contract_reg_project_ref_item ON contract_reg_project_ref(contract_item_id);
CREATE INDEX IF NOT EXISTS idx_contract_clients_item ON contract_clients(contract_item_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_clients ON contract_client_org(clients_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_address ON contract_client_org(address_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_contact ON contract_client_org(contact_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_lr_org ON contract_client_org_legal_rep(client_org_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_org_fr_org ON contract_client_org_financial_resources(client_org_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_person_clients ON contract_client_person(clients_id);
CREATE INDEX IF NOT EXISTS idx_contract_client_person_fr_person ON contract_client_person_financial_resources(client_person_id);
CREATE INDEX IF NOT EXISTS idx_contract_entrusted_person_contractors ON contractor_entrusted_person(contractors_id);
CREATE INDEX IF NOT EXISTS idx_contract_entrusted_person_recent_gov ON contractor_entrusted_person(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_contractors ON contractor_org(contractors_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_address ON contractor_org(address_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_contact ON contractor_org(contact_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_capital_address ON contractor_org(capital_city_repr_address_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_capital_contact ON contractor_org(capital_city_repr_contact_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_lr_org ON contractor_org_legal_rep(contractor_org_id);
CREATE INDEX IF NOT EXISTS idx_contract_org_lr_recent_gov ON contractor_org_legal_rep(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_assigned_person_contractors ON assigned_person(contractors_id);
CREATE INDEX IF NOT EXISTS idx_assigned_person_recent_gov ON assigned_person(recent_gov_function_id);
CREATE INDEX IF NOT EXISTS idx_contract_person_contractors ON contractor_person(contractors_id);
CREATE INDEX IF NOT EXISTS idx_contract_person_recent_gov ON contractor_person(recent_gov_function_id);

CREATE INDEX IF NOT EXISTS idx_code_of_conduct_entry ON code_of_conduct(entry_id);
CREATE INDEX IF NOT EXISTS idx_address_city ON address(city);

-- ========================
-- END OF SCHEMA
-- ========================
SELECT 1;
