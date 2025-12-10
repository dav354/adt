-- BESCHREIBUNG:
-- Diese Abfrage erstellt ein umfassendes Profil von Lobby-Akteuren. 
-- Sie filtert nach Organisationen, die entweder eine hohe finanzielle Macht haben (> 50.000 € Ausgaben) 
-- oder personelle Verflechtungen zur Regierung aufweisen (ehemalige Regierungsmitglieder als Lobbyisten, Vertreter oder betraute Personen). 
-- Dabei werden Daten aus 12 Tabellen verknüpft, darunter Finanzen, Spender, Interessenfelder und diverse Personen-Rollen.
--
SELECT 
    -- Basis-Infos
    re.register_number,
    li.name_text AS organization_name,
    li.legal_form_text,
    
    -- Aggregierte Finanzdaten (Summe Ausgaben & Anzahl Spender)
    SUM(DISTINCT fe.expenses_to_eur) AS total_expenses,
    COUNT(DISTINCT d.id) AS donor_count,
    
    -- Interessen (als kommagetrennter String aggregiert)
    STRING_AGG(DISTINCT cl.de, ', ') AS fields_of_interest,
    
    -- Details zur Person mit Regierungsvergangenheit (Priorität: Lobbyist > Vertreter > Betrauter)
    COALESCE(
        li.last_name || ', ' || li.first_name || ' (Lobbyist)',
        lr.last_name || ', ' || lr.first_name || ' (Legal Rep)',
        ep.last_name || ', ' || ep.first_name || ' (Entrusted)'
    ) AS ex_gov_person_name,
    
    -- Use the Government Function Type (from code_label) as a proxy for the job title
    COALESCE(cl_rgf_li.de, cl_rgf_lr.de, cl_rgf_ep.de) AS past_gov_job,
    COALESCE(rgf_li.end_year_month, rgf_lr.end_year_month, rgf_ep.end_year_month) AS gov_job_ended
    
FROM public.register_entry re

-- 1. Identität & Basisdaten
JOIN public.lobbyist_identity li ON re.id = li.entry_id

-- 2. Finanzen (Achtung: 1:N Beziehung -> kann Zeilen vervielfachen)
LEFT JOIN public.financial_expenses fe ON re.id = fe.entry_id 
    AND fe.fiscal_year_start_ym >= '2021-01' -- Ab 2021

-- 3. Spender (Achtung: noch mehr Zeilenvervielfachung möglich)
LEFT JOIN public.donators d_wrapper ON re.id = d_wrapper.entry_id
LEFT JOIN public.donator_item d ON d_wrapper.id = d.parent_id

-- 4. Interessenfelder (Über Brückentabellen)
JOIN public.activities_interests ai ON re.id = ai.entry_id
JOIN public.field_of_interest foi ON ai.id = foi.activities_id
JOIN public.code_label cl ON foi.label_id = cl.id

-- 5. Personen-Verknüpfungen (Drehtür-Effekt Suche)
LEFT JOIN public.legal_representative lr ON li.id = lr.identity_id
LEFT JOIN public.entrusted_person ep ON li.id = ep.identity_id

-- 6. Regierungsfunktionen für ALLE Personen-Typen prüfen
LEFT JOIN public.recent_government_function rgf_li ON li.recent_gov_function_id = rgf_li.id
LEFT JOIN public.code_label cl_rgf_li ON rgf_li.type_label_id = cl_rgf_li.id

LEFT JOIN public.recent_government_function rgf_lr ON lr.recent_gov_function_id = rgf_lr.id
LEFT JOIN public.code_label cl_rgf_lr ON rgf_lr.type_label_id = cl_rgf_lr.id

LEFT JOIN public.recent_government_function rgf_ep ON ep.recent_gov_function_id = rgf_ep.id
LEFT JOIN public.code_label cl_rgf_ep ON rgf_ep.type_label_id = cl_rgf_ep.id

WHERE 
    -- Relaxed Filter: Either Gov Background OR Big Spender OR Specific Interest
    (
        -- 1. Gov Background (Any of the 3 types)
        li.recent_gov_function_present = true OR 
        lr.recent_gov_function_id IS NOT NULL OR 
        ep.recent_gov_function_present = true
    )
    OR
    (
        -- 2. Big Spender (> 50k)
        fe.expenses_to_eur > 50000
    )

GROUP BY 
    re.id, re.register_number, li.name_text, li.legal_form_text, 
    li.last_name, li.first_name, 
    lr.last_name, lr.first_name, 
    ep.last_name, ep.first_name,
    cl_rgf_li.de, cl_rgf_lr.de, cl_rgf_ep.de,
    rgf_li.end_year_month, rgf_lr.end_year_month, rgf_ep.end_year_month

ORDER BY 
    total_expenses DESC, 
    gov_job_ended DESC
LIMIT 50;
