-- BESCHREIBUNG:
-- "The Data Hoarder" (V3 - ehemals V4) - Aggregations-Monster
-- Ziel: Massive Datenmengen aggregieren und sortieren (I/O & Memory Bound).
-- 
-- Strategie:
-- 1. Scannt ALLE Finanzdaten (kein Zeitfilter), was Index-Scans oft nutzlos macht.
-- 2. Scannt ALLE Spender (über Donator-Wrapper-Join).
-- 3. Erstellt extrem lange Strings via STRING_AGG (Interessen-Liste), was Speicher frisst.
-- 4. Zählt Mitarbeiter aus drei verschiedenen Tabellen zusammen.
-- 5. Sortiert nach aggregierten Werten (SUM, COUNT). Das ist der Killer: Die DB kann nicht 
--    einfach die ersten 50 Treffer nehmen (LIMIT), sondern MUSS erst ALLES berechnen und sortieren, 
--    bevor sie die Top 50 ausgeben kann.
--
-- Erwartetes Ergebnis: Hohe CPU-Last durch Aggregation und hoher RAM-Verbrauch durch Sortierung.

SELECT 
    re.register_number,
    li.name_text AS organization_name,
    
    -- Teure Aggregation: Summe über ALLE Jahre (kein Filter!)
    SUM(COALESCE(fe.expenses_to_eur, 0)) AS total_lifetime_expenses,
    MAX(fe.expenses_to_eur) AS max_yearly_expense,
    
    -- Teure Aggregation: Zähle ALLE Einzelspenden
    COUNT(d.id) AS total_donations_count,
    SUM(COALESCE(d.amount_to_eur, 0)) AS total_donation_volume,
    
    -- Speicher-Fresser: Baue lange Listen von Strings
    -- (Wir limitieren die Länge NICHT, was Postgres zwingt, große Textblobs zu verwalten)
    STRING_AGG(DISTINCT cl_interest.de, '; ') AS all_interests,
    
    -- Verschachtelte Logik für Personen (Summe aus 3 Sub-Counts)
    COUNT(DISTINCT ep.id) + COUNT(DISTINCT lr.id) + COUNT(DISTINCT ne.id) as total_staff_count

FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id

-- 1. Finanzen: LEFT JOIN ohne Filter -> Holt die gesamte Historie
LEFT JOIN public.financial_expenses fe ON re.id = fe.entry_id

-- 2. Spender: Korrekte Join-Kette (Entry -> Donators Wrapper -> Donator Item)
LEFT JOIN public.donators d_wrap ON re.id = d_wrap.entry_id
LEFT JOIN public.donator_item d ON d_wrap.id = d.parent_id

-- 3. Mitarbeiter (Masse statt Klasse - einfach alle joinen)
LEFT JOIN public.entrusted_person ep ON li.id = ep.identity_id
LEFT JOIN public.legal_representative lr ON li.id = lr.identity_id
LEFT JOIN public.named_employee ne ON li.id = ne.identity_id

-- 4. Interessen (Viele zu Viele Beziehung explodiert hier schön)
LEFT JOIN public.activities_interests ai ON re.id = ai.entry_id
LEFT JOIN public.field_of_interest foi ON ai.id = foi.activities_id
LEFT JOIN public.code_label cl_interest ON foi.label_id = cl_interest.id

GROUP BY 
    re.id, re.register_number, li.name_text

-- Der Performance-Killer: Sortierung nach aggregiertem Wert!
-- Postgres MUSS alle Gruppen berechnen, bevor es sortieren und limitieren kann.
ORDER BY total_lifetime_expenses DESC, total_donation_volume DESC
LIMIT 50;