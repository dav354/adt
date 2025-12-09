-- 1. Indizes für häufige Filter/Joins (Index Tuning)
-- Beschleunigt den Zugriff auf Finanzdaten nach Jahr
CREATE INDEX IF NOT EXISTS idx_finance_year_amount
    ON public.financial_expenses (fiscal_year_start_ym, expenses_to_eur);

-- Beschleunigt Joins über die Activities
CREATE INDEX IF NOT EXISTS idx_activities_entry
    ON public.activities_interests (entry_id);


-- Beschleunigt die Suche nach beendeten Regierungsfunktionen und sortiert direkt nach Datum
CREATE INDEX IF NOT EXISTS idx_recent_gov_ended_date
    ON public.recent_government_function (ended, end_year_month DESC);

-- 2. Materialized View: Finanz-Dashboard (Der "Performance-Booster")
-- Diese View "plättet" die 5-fache Join-Hierarchie für das Dashboard
CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_financial_tops AS
SELECT
    cl.de AS field_of_interest,
    COUNT(DISTINCT re.id) as lobbyist_count,
    SUM(fe.expenses_to_eur) as total_spend_max,
    AVG(fe.expenses_to_eur) as avg_spend
FROM public.register_entry re
         JOIN public.activities_interests ai ON re.id = ai.entry_id
         JOIN public.field_of_interest foi ON ai.id = foi.activities_id
         JOIN public.code_label cl ON foi.label_id = cl.id
         LEFT JOIN public.financial_expenses fe ON re.id = fe.entry_id
GROUP BY cl.de;

-- Index auf die View für schnelle Lesegeschwindigkeit
CREATE INDEX IF NOT EXISTS idx_mv_finance_topic ON public.mv_financial_tops(field_of_interest);

-- ============================================================
-- 3. Advanced Indexing: Full-Text-Search & Partial Indexes
-- ============================================================

-- A. Partial Index: Beschleunigt Abfragen auf NUR aktive Lobbyisten drastisch
--    (Der Index ignoriert inaktive Einträge und bleibt klein)
CREATE INDEX IF NOT EXISTS idx_active_lobbyists_only
    ON public.account_details (active_lobbyist)
    WHERE active_lobbyist = true;

-- B. Trigram GIN Index: Für schnelle "LIKE %Suchwort%" Suchen in Namen
--    (Standard B-Tree Indizes können das nicht!)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_trgm_lobbyist_name
    ON public.lobbyist_identity
    USING gin (name_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_trgm_client_name
    ON public.client_org
    USING gin (name gin_trgm_ops);


-- ============================================================
-- 4. Complex Materialized View: "Drehtür-Netzwerk"
-- ============================================================
-- Problem: Personen mit Regierungsvergangenheit verteilen sich auf
--          verschiedene Tabellen (Lobbyisten, Angestellte, Vertreter).
-- Lösung: Wir "union" (vereinen) alle und "flatten" die Struktur für Analysen.

CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_revolving_door_network AS
WITH all_gov_people AS (
    -- 1. Die Lobbyisten selbst
    SELECT entry_id, last_name, first_name, recent_gov_function_id, 'Lobbyist' as role
    FROM public.lobbyist_identity
    WHERE recent_gov_function_present = true
    UNION ALL
    -- 2. Betraute Personen
    SELECT li.entry_id, ep.last_name, ep.first_name, ep.recent_gov_function_id, 'Entrusted Person' as role
    FROM public.entrusted_person ep
    JOIN public.lobbyist_identity li ON ep.identity_id = li.id
    WHERE ep.recent_gov_function_present = true
    UNION ALL
    -- 3. Gesetzliche Vertreter
    SELECT li.entry_id, lr.last_name, lr.first_name, lr.recent_gov_function_id, 'Legal Rep' as role
    FROM public.legal_representative lr
    JOIN public.lobbyist_identity li ON lr.identity_id = li.id
    WHERE lr.recent_gov_function_id IS NOT NULL
)
SELECT
    re.register_number,
    li.name_text as organization_name,
    p.last_name,
    p.first_name,
    p.role,
    rgf.end_year_month,
    cl.de as gov_function_type
FROM all_gov_people p
         JOIN public.register_entry re ON p.entry_id = re.id
         JOIN public.lobbyist_identity li ON re.id = li.entry_id
         JOIN public.recent_government_function rgf ON p.recent_gov_function_id = rgf.id
         LEFT JOIN public.code_label cl ON rgf.type_label_id = cl.id;

-- Index auf die View für schnelle Filterung
CREATE INDEX IF NOT EXISTS idx_mv_revolving_org ON public.mv_revolving_door_network(organization_name);