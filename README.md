# Lobbyregister Ingestor

Werkzeuge, um das deutsche Lobbyregister automatisiert in ein relationales
PostgreSQL‑Schema zu überführen und zu visualisieren.

## Datenbankschema

![schema](docs/ERD.png)

## Voraussetzungen

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (für lokale Entwicklung)
- Docker / Docker Compose (für die Container-Stacks)

## Entwicklung mit uv

1. **Abhängigkeiten installieren und Virtualenv erzeugen**

   ```bash
   uv sync
   ```

2. **Environment vorbereiten**

   Leg eine `.env` im Projekt an (siehe `.env` für ein Beispiel – Standardwerte
   sind bereits eingecheckt). Für lokale tests, nur die datenbank starten

   ```bash
   docker compose up -d db adminer
   ```

3. **Ingestor ausführen**

   ```bash
   uv run python -m lobbyregister_ingestor
   ```

   Wichtige Umgebungsvariablen:

   - `LOBBY_API_URL`, `LOBBY_API_KEY`
   - `ENDPOINT_SEARCH`, `ENDPOINT_DETAIL` für alternative API-Routen
   - `HTTP_CONCURRENCY`, `DB_WORKERS`, `INGEST_QUEUE_SIZE` zur Steuerung der Pipeline
   - `HTTP_MAX_RETRIES`, `HTTP_BACKOFF_FACTOR`, `HTTP_BACKOFF_MAX` für das Retry-Verhalten

## Betrieb über Docker Compose

> [!CAUTION]
>
> Wenn docker compose up ausgeführt wird, started der Ingestor automatisch!

```bash
docker compose up --build
```

Komponenten:

- `db`: PostgreSQL 15 mit Persistenz (`pg_data` Volume)
- `ingest`: Python-Ingestor, wird beim Start einmal ausgeführt
- `adminer`: UI unter <http://localhost:8080>
- `grafana`: Visualisierung unter <http://localhost:3003>
  (Default: `admin` / `admin`, konfigurierbar via `.env`)

**Grafana** provisioniert automatisch eine Datenquelle auf die Postgres-DB sowie das Dashboard.

## Weiterführende Ideen

- Indizes/Materialized Views für häufige Reports
- Automatisierte Dashboards in `grafana/provisioning/dashboards`
- Deduplizierung & Historisierung weiterer Entitäten
