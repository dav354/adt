#!/usr/bin/env python3
import time
import os
import sys
from datetime import datetime
from pathlib import Path
import psycopg

# Konfiguration
DSN = os.getenv("PG_DSN", "postgresql://test:test@localhost:5432/lobby")

# Standard-Ausgabedatei, falls kein Argument übergeben wird
DEFAULT_OUTPUT = Path("docs/benchmark_report.md")

# ==========================================
# DEFINITION DER TEST-SZENARIEN (HOT QUERIES)
# ==========================================
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
    },
    {
        "name": "5. Textsuche (Trigram Index Showcase)",
        "description": "Suche nach Firmen/Personen mit Teilstring-Match (z.B. 'Energy'). Profitiert von GIN-Indizes.",
        "sql": """
               SELECT name_text, identity
               FROM public.lobbyist_identity
               WHERE name_text ILIKE '%Energy%'
               LIMIT 100;
               """
    },
    {
        "name": "6. Drehtür-Analyse (Complex MV)",
        "description": "Aggregierte Liste aller Personen mit Regierungsamt aus der Materialized View (falls vorhanden).",
        "sql": """
               SELECT organization_name, last_name, gov_function_type
               FROM public.mv_revolving_door_network
               WHERE end_year_month > '2020-01'
               ORDER BY end_year_month DESC
               LIMIT 500;
               """
    }
]

def _sum_buffers(plan_node):
    """
    Rekursive Funktion, um Buffer-Stats (Hits/Reads) aus dem JSON-Plan zu summieren.
    """
    hits = plan_node.get('Shared Hit Blocks', 0)
    reads = plan_node.get('Shared Read Blocks', 0)

    if 'Plans' in plan_node:
        for child in plan_node['Plans']:
            c_hits, c_reads = _sum_buffers(child)
            hits += c_hits
            reads += c_reads
    return hits, reads

def run_benchmark(output_file: Path):
    results = []
    print(f"🚀 Starte Benchmark auf {DSN}...")
    print(f"📄 Report wird gespeichert in: {output_file}")

    try:
        with psycopg.connect(DSN) as conn:
            for scenario in BENCHMARK_QUERIES:
                print(f"   Messe: {scenario['name']}...")

                try:
                    # BUFFERS Option liefert uns I/O Statistiken
                    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {scenario['sql']}"

                    start_wall = time.time()
                    with conn.cursor() as cur:
                        cur.execute(explain_sql)
                        plan_raw = cur.fetchone()[0]
                    end_wall = time.time()

                    plan_node = plan_raw[0]
                    exec_time_ms = plan_node.get('Execution Time', 0.0)
                    planning_time_ms = plan_node.get('Planning Time', 0.0)
                    total_cost = plan_node['Plan']['Total Cost']

                    # Buffer-Analyse extrahieren
                    hits, reads = _sum_buffers(plan_node['Plan'])

                    results.append({
                        "name": scenario['name'],
                        "desc": scenario['description'],
                        "exec_time_ms": exec_time_ms,
                        "plan_time_ms": planning_time_ms,
                        "hits": hits,
                        "reads": reads,
                        "wall_time_s": end_wall - start_wall,
                        "total_cost": total_cost,
                        "error": None
                    })
                except psycopg.errors.UndefinedTable:
                    conn.rollback()
                    print(f"      ⚠️  Überspringe (Tabelle/View fehlt): {scenario['name']}")
                    results.append({
                        "name": scenario['name'],
                        "desc": scenario['description'],
                        "exec_time_ms": 0,
                        "hits": 0, "reads": 0,
                        "plan_time_ms": 0,
                        "total_cost": 0,
                        "error": "View/Tabelle fehlt (Optimierung ausstehend)"
                    })
                except Exception as e:
                    conn.rollback()
                    print(f"      ❌ Fehler: {e}")
                    results.append({
                        "name": scenario['name'],
                        "desc": scenario['description'],
                        "exec_time_ms": 0,
                        "hits": 0, "reads": 0,
                        "plan_time_ms": 0,
                        "total_cost": 0,
                        "error": str(e)
                    })

        write_markdown_report(results, output_file)
        print("✅ Benchmark abgeschlossen.")

    except Exception as e:
        print(f"🔥 Kritischer Verbindungsfehler: {e}")
        sys.exit(1)

def write_markdown_report(results, filepath):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = filepath.name

    md_content = f"""# 📊 Benchmark Report: {filename}

**Datum:** {timestamp}  
**Datenbank:** PostgreSQL  
**Legende:** Hits = Cache Treffer (RAM), Reads = Disk I/O (Festplatte)

| Szenario | Execution (ms) | I/O (Hits/Reads) | Cost | Anmerkung |
| :--- | :--- | :--- | :--- | :--- |
"""

    for r in results:
        if r['error']:
            md_content += f"| {r['name']} | - | - | - | ❌ {r['error']} |\n"
        else:
            exec_str = f"{r['exec_time_ms']:.2f}"
            # Highlight langsame Queries fett
            if r['exec_time_ms'] > 500:
                exec_str = f"**{exec_str}**"

            io_str = f"{r['hits']} / {r['reads']}"
            if r['reads'] > 0:
                # Highlight wenn Disk I/O stattfindet (Cold Cache Indikator)
                io_str += " 💾"

            md_content += f"| {r['name']} | {exec_str} | {io_str} | {r['total_cost']:.2f} | |\n"

    md_content += "\n## SQL Details\n\n"
    for i, r in enumerate(results):
        sql_text = BENCHMARK_QUERIES[i]['sql'].strip()
        md_content += f"### {r['name']}\nRunning: `{r['desc']}`\n```sql\n{sql_text}\n```\n\n"

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_file = Path(sys.argv[1])
    else:
        target_file = DEFAULT_OUTPUT

    run_benchmark(target_file)