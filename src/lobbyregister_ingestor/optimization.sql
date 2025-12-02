-- 1. Indizes für häufige Filter/Joins (Index Tuning)
-- Beschleunigt den Zugriff auf Finanzdaten nach Jahr
CREATE INDEX IF NOT EXISTS idx_finance_year_amount
    ON public.financial_expenses (fiscal_year_start_ym, expenses_to_eur);

-- Beschleunigt Joins über die Activities
CREATE INDEX IF NOT EXISTS idx_activities_entry
    ON public.activities_interests (entry_id);

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