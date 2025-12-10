-- BESCHREIBUNG:
-- Diese Abfrage ('Endgegner V2') führt eine komplexe forensische Analyse durch. 
-- Sie nutzt Window Functions, um Ausgabentrends (Wachstum zum Vorjahr) zu berechnen, 
-- identifiziert geografische Lobby-Cluster über Postleitzahlen und sucht nach verdächtigen Namensgleichheiten 
-- ('Interlocking Directorates') zwischen Lobbyisten und betrauten Personen anderer Firmen. 
-- Das Ergebnis wird aggregiert und teilweise als JSON-Objekt ausgegeben.
--
-- COMPLEXITY LEVEL: EXTREME
-- Features: Window Functions, CTEs, String-Joins, JSON Aggregation, Subqueries

WITH 
-- 1. Financial Trend Analysis (Window Functions)
-- Berechnet das Wachstum der Ausgaben pro Firma im Vergleich zum Vorjahr
spending_trends AS (
    SELECT 
        entry_id,
        fiscal_year_start_ym,
        expenses_to_eur,
        -- Hole den Wert der vorherigen Zeile (im partitionierten Fenster)
        LAG(expenses_to_eur) OVER (
            PARTITION BY entry_id 
            ORDER BY fiscal_year_start_ym ASC
        ) as prev_year_expenses
    FROM public.financial_expenses
    WHERE fiscal_year_start_ym IS NOT NULL
),
-- Filtere nur Firmen, die ihr Budget erhöht haben (oder neu sind)
growing_spenders AS (
    SELECT entry_id, expenses_to_eur 
    FROM spending_trends 
    WHERE (expenses_to_eur > prev_year_expenses) OR (prev_year_expenses IS NULL AND expenses_to_eur > 50000)
),

-- 2. Address Clustering (Aggregation)
-- Identifiziere "Lobby-Hotspots": PLZ-Gebiete mit mehr als 5 registrierten Lobbyisten
lobby_hotspots AS (
    SELECT 
        a.zip_code, 
        a.city, 
        COUNT(li.id) as neighbors_count
    FROM public.lobbyist_identity li
    JOIN public.address a ON li.address_id = a.id
    WHERE a.zip_code IS NOT NULL
    GROUP BY a.zip_code, a.city
    HAVING COUNT(li.id) > 2 -- Kleine Cluster reichen für den Test
),

-- 3. Name Network (The CPU Killer)
-- Finde Lobbyisten, deren Nachname identisch ist mit einer "Betrauten Person" einer ANDEREN Firma
-- (Simuliert Netzwerk-Suche / Vetternwirtschaft)
suspicious_names AS (
    SELECT DISTINCT 
        li.entry_id, 
        li.last_name
    FROM public.lobbyist_identity li
    JOIN public.entrusted_person ep ON li.last_name = ep.last_name
    JOIN public.lobbyist_identity li_other ON ep.identity_id = li_other.id
    WHERE li.entry_id != li_other.entry_id -- Nicht die eigene Firma
)

-- MAIN QUERY
SELECT 
    re.register_number,
    li.name_text as organization,
    
    -- Aggregierte Finanz-Info aus CTE
    MAX(gs.expenses_to_eur) as max_recent_spending,
    
    -- Info aus Address-Cluster CTE
    COALESCE(lh.city, 'Unknown') as location_cluster,
    COALESCE(lh.neighbors_count, 0) as cluster_size,
    
    -- Komplexes JSON-Objekt bauen (CPU intensiv)
    JSON_BUILD_OBJECT(
        'fields_of_interest', JSON_AGG(DISTINCT cl.de),
        'network_hits', COUNT(DISTINCT sn.last_name),
        'donator_count', COUNT(DISTINCT don.id)
    ) as audit_report
    
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id

-- Join Financial CTE
LEFT JOIN growing_spenders gs ON re.id = gs.entry_id

-- Join Address Cluster CTE
LEFT JOIN public.address a ON li.address_id = a.id
LEFT JOIN lobby_hotspots lh ON a.zip_code = lh.zip_code AND a.city = lh.city

-- Join "Suspicious Names" CTE
LEFT JOIN suspicious_names sn ON re.id = sn.entry_id

-- Join Interests for Aggregation
LEFT JOIN public.activities_interests ai ON re.id = ai.entry_id
LEFT JOIN public.field_of_interest foi ON ai.id = foi.activities_id
LEFT JOIN public.code_label cl ON foi.label_id = cl.id

-- Join Donators just for volume
LEFT JOIN public.donators don_wrap ON re.id = don_wrap.entry_id
LEFT JOIN public.donator_item don ON don_wrap.id = don.parent_id

GROUP BY 
    re.id, re.register_number, li.name_text, lh.city, lh.neighbors_count
    
HAVING COUNT(DISTINCT sn.last_name) > 0 -- Nur Firmen mit Namens-Matches anzeigen
   OR MAX(gs.expenses_to_eur) > 50000

ORDER BY cluster_size DESC, max_recent_spending DESC
LIMIT 100;