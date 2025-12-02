# 📊 Lobbyregister Performance Benchmark

**Datum:** 2025-12-02 23:46:35  
**Datenbank:** PostgreSQL

Dieser Bericht wurde automatisch generiert. Er misst die Performance kritischer Analyse-Abfragen ("Hot Queries").

## Zusammenfassung

| Szenario | Execution Time (ms) | Planning Time (ms) | Kosten (Cost) |
| :--- | :--- | :--- | :--- |
| 1. Finanz-Heatmap (Themenfelder) | 44.77 | 2.37 | 4933.09 |
| 2. Top-Lobbyisten (Kosten-Analyse) | 11.19 | 6.46 | 1174.86 |
| 3. Drehtür-Effekt (Regierungsfunktionen) | 1.36 | 4.03 | 466.59 |
| 4. Netzwerk-Analyse (Auftraggeber) | 7.19 | 4.10 | 60.63 |

## Details & SQL

### 1. Finanz-Heatmap (Themenfelder)
_Aggregiert Ausgaben pro Themenfeld. Join über 5 Tabellen._

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
_Findet die Organisationen mit den höchsten Ausgaben. Join Identity & Expenses._

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
_Sucht Lobbyisten mit vorheriger Regierungsfunktion. Filter & Join._

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
_Verknüpft Einträge mit ihren Auftraggebern (Clients)._

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

