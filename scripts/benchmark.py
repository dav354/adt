#!/usr/bin/env python3
import json
import time
import os
from datetime import datetime
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

# Konfiguration
DSN = os.getenv("PG_DSN", "postgresql://test:test@localhost:5432/lobby")
OUTPUT_FILE = Path("docs/benchmark_report.md")

# ==========================================
# DEFINITION DER TEST-SZENARIEN (HOT QUERIES)
# ==========================================
# Diese Queries decken verschiedene Aspekte deines Schemas ab (Joins, Aggregationen, Filter)
BENCHMARK_QUERIES = [
    {
        "name": "1. Finanz-Heatmap (Themenfelder)",
        "description": "Aggregiert Ausgaben pro Themenfeld. Join über 5 Tabellen.",
        "sql": """
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
               """
    },
    {
        "name": "2. Top-Lobbyisten (Kosten-Analyse)",
        "description": "Findet die Organisationen mit den höchsten Ausgaben. Join Identity & Expenses.",
        "sql": """
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
               """
    },
    {
        "name": "3. Drehtür-Effekt (Regierungsfunktionen)",
        "description": "Sucht Lobbyisten mit vorheriger Regierungsfunktion. Filter & Join.",
        "sql": """
               SELECT
                   li.last_name,
                   li.first_name,
                   rgf.end_year_month
               FROM public.lobbyist_identity li
                        JOIN public.recent_government_function rgf ON li.recent_gov_function_id = rgf.id
               WHERE rgf.ended = true
               ORDER BY rgf.end_year_month DESC;
               """
    },
    {
        "name": "4. Netzwerk-Analyse (Auftraggeber)",
        "description": "Verknüpft Einträge mit ihren Auftraggebern (Clients).",
        "sql": """
               SELECT
                   re.register_number,
                   co.name as client_name,
                   co.legal_form_text
               FROM public.register_entry re
                        JOIN public.client_identity ci ON re.id = ci.entry_id
                        JOIN public.client_org co ON ci.id = co.client_identity_id
               WHERE ci.clients_present = true
               LIMIT 1000;
               """
    }
]

def run_benchmark():
    results = []

    print(f"🚀 Starte Benchmark auf {DSN}...")

    with psycopg.connect(DSN) as conn:
        for scenario in BENCHMARK_QUERIES:
            print(f"   Messe: {scenario['name']}...")

            # Wir nutzen EXPLAIN (ANALYZE, FORMAT JSON) um exakte DB-Metriken zu bekommen
            # Das ist genauer als Python time(), da es Netzwerk-Latenz ignoriert
            explain_sql = f"EXPLAIN (ANALYZE, FORMAT JSON) {scenario['sql']}"

            start_wall = time.time()
            with conn.cursor() as cur:
                cur.execute(explain_sql)
                plan_raw = cur.fetchone()[0]

            end_wall = time.time()

            # Extrahiere Metriken aus dem JSON Plan
            # Der Plan ist eine Liste mit einem Element
            plan_node = plan_raw[0]
            exec_time_ms = plan_node.get('Execution Time', 0.0)
            planning_time_ms = plan_node.get('Planning Time', 0.0)

            results.append({
                "name": scenario['name'],
                "desc": scenario['description'],
                "exec_time_ms": exec_time_ms,
                "plan_time_ms": planning_time_ms,
                "wall_time_s": end_wall - start_wall,
                "total_cost": plan_node['Plan']['Total Cost']
            })

    write_markdown_report(results)
    print(f"✅ Benchmark fertig. Bericht gespeichert in: {OUTPUT_FILE}")

def write_markdown_report(results):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md_content = f"""# 📊 Lobbyregister Performance Benchmark

**Datum:** {timestamp}  
**Datenbank:** PostgreSQL

Dieser Bericht wurde automatisch generiert. Er misst die Performance kritischer Analyse-Abfragen ("Hot Queries").

## Zusammenfassung

| Szenario | Execution Time (ms) | Planning Time (ms) | Kosten (Cost) |
| :--- | :--- | :--- | :--- |
"""

    for r in results:
        # Formatierung: Fett gedruckt, wenn sehr langsam (>500ms)
        exec_str = f"{r['exec_time_ms']:.2f}"
        if r['exec_time_ms'] > 500:
            exec_str = f"**{exec_str}** ⚠️"

        md_content += f"| {r['name']} | {exec_str} | {r['plan_time_ms']:.2f} | {r['total_cost']:.2f} |\n"

    md_content += "\n## Details & SQL\n\n"

    for i, r in enumerate(results):
        orig_sql = BENCHMARK_QUERIES[i]['sql'].strip()
        md_content += f"### {r['name']}\n"
        md_content += f"_{r['desc']}_\n\n"
        md_content += "```sql\n" + orig_sql + "\n```\n\n"

    # Verzeichnis sicherstellen
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Datei schreiben (anhängen oder überschreiben? Hier: Überschreiben für den aktuellen Run)
    # Wenn du eine Historie willst, könntest du den Dateinamen mit Timestamp versehen.
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)

if __name__ == "__main__":
    run_benchmark()