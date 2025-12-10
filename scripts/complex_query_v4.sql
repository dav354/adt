-- BESCHREIBUNG:
-- "The Interest Web" (V5) - High-Volume Join Explosion
-- Ziel: Erzeugung massiver Zwischenergebnismengen (Intermediate Result Sets) durch N:M Joins.
-- 
-- Strategie:
-- Wir suchen nach der "Nadel im Heuhaufen", aber so, dass der Heuhaufen riesig wird.
-- Wir verknüpfen einen Lobbyisten mit sich selbst über DREI verschiedene Pfade, 
-- die sich alle im "Interessenfeld" (Field of Interest) treffen.
-- 
-- Pfad 1: Lobbyist -> Allgemeine Interessen
-- Pfad 2: Lobbyist -> Verträge -> Vertrags-Interessen
-- Pfad 3: Lobbyist -> Gesetzesvorhaben -> Projekt-Interessen
-- 
-- Wenn ein Lobbyist z.B. "Energie" in allen 3 Bereichen angibt, explodiert der Join,
-- da wir alle Kombinationen von Verträgen und Projekten bilden, die dieses Thema haben.
--
-- Zusätzlich joinen wir Detail-Tabellen (Auftragnehmer, Ministerien), um die Zeilenbreite zu erhöhen.
-- Sortierung nach Text-Länge zwingt die DB, die Strings wirklich zu verarbeiten.

SELECT 
    re.register_number,
    li.name_text AS lobbyist_name,
    cl.de AS common_interest_topic,
    
    -- Aggregationen, um die Explosion wieder einzufangen
    COUNT(DISTINCT c.id) AS num_contracts_with_topic,
    COUNT(DISTINCT rp.id) AS num_projects_with_topic,
    
    -- Teure String-Operationen auf den gejointen Details
    STRING_AGG(DISTINCT co.name, ' | ') AS contractors_involved,
    STRING_AGG(DISTINCT rpi.title, ' | ') AS projects_involved,
    STRING_AGG(DISTINCT lm.title, ' | ') AS leading_ministries
    
FROM public.register_entry re
JOIN public.lobbyist_identity li ON re.id = li.entry_id

-- 1. Basis-Interessen
JOIN public.activities_interests ai ON re.id = ai.entry_id
JOIN public.field_of_interest foi ON ai.id = foi.activities_id
JOIN public.code_label cl ON foi.label_id = cl.id

-- 2. Vertrags-Pfad (Deep Join)
JOIN public.contracts c ON re.id = c.entry_id
JOIN public.contract_item ci ON c.id = ci.parent_id
JOIN public.contract_field_of_interest cfoi ON ci.id = cfoi.contract_item_id AND cfoi.label_id = cl.id -- Join über Interest ID
-- Details dazu joinen (für "Breite")
LEFT JOIN public.contract_contractors cc ON ci.id = cc.contract_item_id
LEFT JOIN public.contractor_org co ON cc.id = co.contractors_id

-- 3. Gesetzes-Pfad (Deep Join)
JOIN public.regulatory_projects rp ON re.id = rp.entry_id
JOIN public.regulatory_project_item rpi ON rp.id = rpi.parent_id
JOIN public.reg_project_field_of_interest rpfoi ON rpi.id = rpfoi.project_item_id AND rpfoi.label_id = cl.id -- Join über Interest ID
-- Details dazu joinen
LEFT JOIN public.reg_project_printed_matter rppm ON rpi.id = rppm.project_item_id
LEFT JOIN public.reg_project_printed_matter_ministry rppmm ON rppm.id = rppmm.printed_matter_id
LEFT JOIN public.leading_ministry lm ON rppmm.ministry_id = lm.id

GROUP BY 
    re.register_number, 
    li.name_text, 
    cl.de

-- Sortiere nach der Länge des erzeugten Strings (CPU-intensiv)
ORDER BY LENGTH(STRING_AGG(DISTINCT rpi.title, ' | ')) DESC
LIMIT 50;
