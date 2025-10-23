# Lobbyregister Ingestor

Auswertung und Visualisierung der deutschen Lobbyregister Daten.

<https://api.lobbyregister.bundestag.de/rest/v2/swagger-ui/#/Statistiken/getStatisticsRegisterEntries>

## Architektur

- `Postgres` Datenbank (Docker)
- `Python` Ingestion-Skript (`lobbyregister_ingestor`, uv + httpx + SQLAlchemy + psycopg)
- Visualisierung / Reporting (z. B. Grafana – Portfolio 4)

## Voraussetzungen

- Docker & Docker Compose
- Nix (>= 2.18) zum Bereitstellen der Entwicklungsumgebung mit `uv`

## Setup & Nutzung

1. **Environment-Datei anlegen:**

   ```bash
   cp .env.example .env
   ```

   Passe bei Bedarf `POSTGRES_PASSWORD`, `DATABASE_URL` und weitere Variablen an.

1. **Dev-Shell starten (installiert automatisch alle Python-Abhängigkeiten über uv):**

   ```bash
   nix develop
   ```

   Beim ersten Start erzeugt der `shellHook` eine `.venv/` via `uv sync` und aktiviert sie automatisch.

1. **Stack starten und Daten laden:**

   ```bash
   docker compose up --build
   ```

   - Service `db`: Postgres 18 (Port 5432)
   - Service `ingest`: Läuft einmalig, ruft sämtliche relevanten Lobbyregister-Endpunkte auf und schreibt sie in ein relational normalisiertes Schema.

1. **Verbindung zur Datenbank (optional):**

   ```bash
   psql postgresql://lobby:changeme@localhost:5432/lobbyregister
   ```

   Tabelle prüfen:

   ```sql
   SELECT source_date, source FROM statistics_register_entries;
   ```

## Lokales Ausführen des Ingestion-Skripts

Innerhalb der `nix develop` Shell steht die virtuelle Umgebung bereit:

```bash
uv run ingest-register
```

Stelle sicher, dass in deiner `.env` die `DATABASE_URL` für die Ziel-DB gesetzt ist (siehe `.env.example`). Alternativ kannst du die Variable auch nur für den Aufruf setzen:

   ```bash
   POSTGRES_USER=lobby \
   POSTGRES_PASSWORD=changeme \
   POSTGRES_DB=lobbyregister \
   POSTGRES_HOST=localhost \
   uv run ingest-register
   ```

Optionale Variablen:

- `POSTGRES_HOST` – Hostname des Datenbankservers (`db` im Docker-Compose-Setup, `localhost` für lokale Runs)
- `POSTGRES_PORT` – Port der Datenbankverbindung (Standard 5432)
- `LOBBY_API_URL` – überschreibt das Standard-Endpoint
- `LOBBY_API_TIMEOUT` – Timeout in Sekunden (Standard 30)
- `LOBBY_API_MAX_CONCURRENCY` – Maximale Anzahl paralleler API-Anfragen (Standard 5)
- `DATABASE_CONNECT_TIMEOUT` – Verbindungs-Wartezeit (Standard 60)

## Datenmodell

- Das relationale Schema wird zur Laufzeit aus `api-docs-lobbyregister.yaml` abgeleitet (`schema_builder.py`) und anschließend per SQLAlchemy (`metadata.create_all()`) erstellt.
- Die wichtigsten Tabellen: `register_entries`, `register_entries__account_details`, `register_entries__lobbyist_identity`, `register_entry_versions`, `statistics_register_entries`. Verschachtelte Objekte und Arrays hängen über `parent_id`/`position` am übergeordneten Datensatz.
- Die Ingestion läuft vollständig asynchron (`httpx.AsyncClient`, SQLAlchemy Async Engine mit `asyncpg`) und validiert alle eingehenden Payloads über Pydantic-Modelle, bevor sie in die Datenbank geschrieben werden. Datenbankzugangsdaten werden ausschließlich über die `POSTGRES_*` Umgebungsvariablen bezogen.

Beim erneuten Ingest werden Datensätze anhand natürlicher Schlüssel (z. B. `register_number`, `version`, `source_date`) idempotent aktualisiert.

## Weiteres Vorgehen (Portfolios)

- **Portfolio 1:** Auswahl Zielsystem / Szenario
- **Portfolio 2:** Daten befüllen (durch dieses Setup abgedeckt)
- **Portfolio 3:** Tuning (z. B. Indizes, Materialized Views)
- **Portfolio 4:** Freie Ideen (Visualisierung, Dashboards, zusätzliche Analysen)
