# 📊 Benchmark Report: benchmark_report.md

**Datum:** 2025-12-10 15:41:12  
**Datenbank:** PostgreSQL  
**Legende:** Hits = Cache Treffer (RAM), Reads = Disk I/O (Festplatte)

| Szenario | Execution (ms) | I/O (Hits/Reads) | Cost | Anmerkung |
| :--- | :--- | :--- | :--- | :--- |
| 1. Finanz-Heatmap (Themenfelder) | 81.19 | 25 / 20119 💾 | 5727.77 | |
| 2. Top-Lobbyisten (Kosten-Analyse) | 9.10 | 2380 / 985 💾 | 1396.43 | |
| 3. Drehtür-Effekt (Regierungsfunktionen) | 1.68 | 4161 / 135 💾 | 593.58 | |
| 4. Netzwerk-Analyse (Auftraggeber) | 3.90 | 874 / 169 💾 | 89.50 | |
| 5. Textsuche (Trigram Index Showcase) | 1.11 | 108 / 15 💾 | 40.02 | |
| 6. Drehtür-Analyse (Complex MV) | 1.05 | 0 / 57 💾 | 79.21 | |

## SQL Details

### 1. Finanz-Heatmap (Themenfelder)
Running: `Aggregiert Ausgaben pro Themenfeld. Join über 5 Tabellen.`
```sql
SELECT
                   cl.de as thema,
                   COUNT(*) as anzahl,
                   SUM(fe.expenses_to_eur) as total_eur
               FROM public.register_entry re
                        JOIN public.financial_expenses fe ON re.id = fe.entry_id
                        JOIN public.activities_interests ai ON re.id = ai.entry_id
                        JOIN public.field_of_interest foi ON ai.id = foi.activities_id
                        JOIN public.code_label cl ON foi.label_id = cl.id
               GROUP BY cl.de
               ORDER BY total_eur DESC
               LIMIT 20;
```

### 2. Top-Lobbyisten (Kosten-Analyse)
Running: `Findet die Organisationen mit den höchsten Ausgaben. Join Identity & Expenses.`
```sql
SELECT
                   li.name_text,
                   li.company_name,
                   fe.expenses_to_eur
               FROM public.register_entry re
                        JOIN public.lobbyist_identity li ON re.id = li.entry_id
                        JOIN public.financial_expenses fe ON re.id = fe.entry_id
               WHERE fe.expenses_to_eur IS NOT NULL
               ORDER BY fe.expenses_to_eur DESC
               LIMIT 50;
```

### 3. Drehtür-Effekt (Regierungsfunktionen)
Running: `Sucht Lobbyisten mit vorheriger Regierungsfunktion. Filter & Join.`
```sql
SELECT
                   li.last_name,
                   li.first_name,
                   rgf.end_year_month
               FROM public.lobbyist_identity li
                        JOIN public.recent_government_function rgf ON li.recent_gov_function_id = rgf.id
               WHERE rgf.ended = true
               ORDER BY rgf.end_year_month DESC;
```

### 4. Netzwerk-Analyse (Auftraggeber)
Running: `Verknüpft Einträge mit ihren Auftraggebern (Clients).`
```sql
SELECT
                   re.register_number,
                   co.name as client_name,
                   co.legal_form_text
               FROM public.register_entry re
                        JOIN public.client_identity ci ON re.id = ci.entry_id
                        JOIN public.client_org co ON ci.id = co.client_identity_id
               WHERE ci.clients_present = true
               LIMIT 1000;
```

### 5. Textsuche (Trigram Index Showcase)
Running: `Suche nach Firmen/Personen mit Teilstring-Match (z.B. 'Energy'). Profitiert von GIN-Indizes.`
```sql
SELECT name_text, identity
               FROM public.lobbyist_identity
               WHERE name_text ILIKE '%Energy%'
               LIMIT 100;
```

### 6. Drehtür-Analyse (Complex MV)
Running: `Aggregierte Liste aller Personen mit Regierungsamt aus der Materialized View (falls vorhanden).`
```sql
SELECT organization_name, last_name, gov_function_type
               FROM public.mv_revolving_door_network
               WHERE end_year_month > '2020-01'
               ORDER BY end_year_month DESC
               LIMIT 500;
```

