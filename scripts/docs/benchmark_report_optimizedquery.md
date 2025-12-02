# 📊 Lobbyregister Performance Benchmark

**Datum:** 2025-12-03 00:12:04  
**Datenbank:** PostgreSQL

Dieser Bericht wurde automatisch generiert. Er misst die Performance kritischer Analyse-Abfragen ("Hot Queries").

## Zusammenfassung

| Szenario | Execution Time (ms) | Planning Time (ms) | Kosten (Cost) |
| :--- | :--- | :--- | :--- |
| 1. Finanz-Heatmap (Themenfelder) [OPTIMIERT] | 0.12 | 0.41 | 6.92 |
| 2. Top-Lobbyisten (Kosten-Analyse) | 9.38 | 0.75 | 1396.43 |
| 3. Drehtür-Effekt (Regierungsfunktionen) | 0.95 | 0.29 | 598.46 |
| 4. Netzwerk-Analyse (Auftraggeber) | 0.39 | 0.34 | 89.50 |

## Details & SQL

### 1. Finanz-Heatmap (Themenfelder) [OPTIMIERT]
_Aggregiert Ausgaben via Materialized View (statt 5-fach Join)._

```sql
SELECT field_of_interest, total_spend_max
               FROM public.mv_financial_tops
               ORDER BY total_spend_max DESC
               LIMIT 20;
```

### 2. Top-Lobbyisten (Kosten-Analyse)
_Findet die Organisationen mit den höchsten Ausgaben._

```sql
SELECT li.name_text, li.company_name, fe.expenses_to_eur
               FROM public.register_entry re
                        JOIN public.lobbyist_identity li ON re.id = li.entry_id
                        JOIN public.financial_expenses fe ON re.id = fe.entry_id
               WHERE fe.expenses_to_eur IS NOT NULL
               ORDER BY fe.expenses_to_eur DESC LIMIT 50;
```

### 3. Drehtür-Effekt (Regierungsfunktionen)
_Sucht Lobbyisten mit vorheriger Regierungsfunktion._

```sql
SELECT li.last_name, li.first_name, rgf.end_year_month
               FROM public.lobbyist_identity li
                        JOIN public.recent_government_function rgf ON li.recent_gov_function_id = rgf.id
               WHERE rgf.ended = true
               ORDER BY rgf.end_year_month DESC;
```

### 4. Netzwerk-Analyse (Auftraggeber)
_Verknüpft Einträge mit ihren Auftraggebern._

```sql
SELECT re.register_number, co.name, co.legal_form_text
               FROM public.register_entry re
                        JOIN public.client_identity ci ON re.id = ci.entry_id
                        JOIN public.client_org co ON ci.id = co.client_identity_id
               WHERE ci.clients_present = true LIMIT 1000;
```

