# Lobbyregister Ingestor

Auswertung und Visualisierung der Daten des deutschen Lobbyregisters.

API-Dokumentation: <https://api.lobbyregister.bundestag.de/rest/v2/swagger-ui/>

## Architekturüberblick

- **PostgreSQL 18** (Docker) als Ziel-Datenbank
- **Python/uv**-basierter Ingestor (`lobbyregister_ingestor`) mit `httpx`, `SQLAlchemy` und `asyncpg`
- optionale Visualisierung/Analysen (z. B. Grafana) auf dem erzeugten Schema

## Voraussetzungen

- Docker & Docker Compose

## Setup

1. **Stack starten und Daten laden**

   ```bash
   docker compose up --build
   ```

   - Service `db`: Postgres (Port 5432)
   - Service `ingest`: ruft das Lobbyregister ab und importiert die Daten in das normalisierte Schema
   - Service `adminer`: Web-Oberfläche unter <http://localhost:8080>

2. **(Optional) Datenbank inspizieren**

   ```bash
   psql postgresql://lobby:changeme@localhost:5432/lobby
   ```

   Beispielabfrage:

   ```sql
   SELECT COUNT(*) FROM register_entries;
   ```

## Ingestor lokal ausführen

Die Dev-Shell enthält bereits die aktivierte virtuelle Umgebung:

```bash
uv run ingest-register
```

Die `POSTGRES_*`-Variablen können entweder in `.env` gesetzt sein oder ad-hoc beim Aufruf:

```bash
POSTGRES_USER=lobby \
POSTGRES_PASSWORD=changeme \
POSTGRES_DB=lobby \
POSTGRES_HOST=localhost \
DATABASE_APPLY_SCHEMA=true \
uv run ingest-register
```

Weitere Parameter:

- `LOBBY_API_URL` – Basis-URL der API (Standard: `https://api.lobbyregister.bundestag.de/rest/v2`)
- `LOBBY_API_TIMEOUT` – Timeout in Sekunden (Standard 30)
- `LOBBY_API_MAX_CONCURRENCY` – gleichzeitige API-Requests (Standard 5)
- `DATABASE_CONNECT_TIMEOUT` – Wartezeit beim DB-Verbindungsaufbau (Standard 60)

Alle Einstellungen beziehen der Ingestor und Docker-Container über Umgebungsvariablen.

## Interna & Datenmodell

- Das relationale Schema wird zur Laufzeit aus dem Beispiel-Datensatz `scheme.json` generiert (`src/lobbyregister_ingestor/schema.py`). Verschachtelte Objekte werden zu separaten Tabellen (1:n), Arrays zu Positionslisten oder Werttabellen.
- Die Persistenz-Schicht (`persistence.py`) übernimmt Typkonvertierung, setzt Fremdschlüssel sowie `ON CONFLICT DO UPDATE` für natürliche Schlüssel wie `register_number`.
- Der Ingestor (`ingest.py`) ruft ausschließlich die Detail-Endpoints `/registerentries/{registerNumber}` ab, nutzt dabei asynchrone HTTP-Requests und schreibt die Ergebnisse transaktional in die Datenbank.
- Fehlerhafte API-Antworten werden mit gekürzter Payload-Vorschau (max. 500 Zeichen) geloggt, um Debugging zu erleichtern.

## Weiterführende Arbeiten

- Tuning (Indizes, Materialized Views, Partitionierung)
- Analyse/Reporting (Grafana-Dashboards zur viaualisierung mit autoprovisioning der datenquelle und auch dashboards)
- Weitere Datenquellen oder alternative Schemata auf Basis der JSON-Definition
