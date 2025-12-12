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

## Grafana Dashboards

Die Visualisierung der Daten erfolgt über vor-konfigurierte Grafana Dashboards, die verschiedene Aspekte des Lobbyregisters beleuchten.

### 1. High-Level Overview

Zentrale KPIs auf einen Blick: Anzahl aktiver Lobbyisten, kumuliertes Finanzvolumen, personelle Schlagkraft (FTE) und die Verteilung der Themenfelder.
![Overview Dashboard](docs/portfolio_4/figures/dashboard_overview.png)

### 2. Geographic Insights

Eine interaktive Karte zeigt die globale und nationale Verteilung der Akteure. Detaillierte Filter ermöglichen Analysen bis auf Städte-Ebene (hier am Beispiel **Würzburg**).
![Geo Dashboard](docs/portfolio_4/figures/dashboard_geo.png)
![City Dashboard](docs/portfolio_4/figures/dashboard_city.png)

### 3. Organization Profiler

Eine 360°-Detailansicht für einzelne Akteure. Am Beispiel der **Fraunhofer-Gesellschaft** werden Finanzhistorie, Mitarbeiterstruktur, Mitgliedschaften und spezifische Gesetzesvorhaben transparent gemacht.
![Organization Dashboard](docs/portfolio_4/figures/dashboard_organization.png)

### 4. Transparenz & Compliance

Listet Akteure auf, die Finanzangaben verweigern oder Jahresberichte schuldig bleiben, und identifiziert potenzielle Compliance-Lücken.
![Transparency Dashboard](docs/portfolio_4/figures/dashboard_compliance.png)

### 5. Advanced Analytics

Visualisiert komplexe Netzwerke ("Wer kennt wen?") und legislative Fußabdrücke (Einflussnahme auf spezifische Gesetze).
![Advanced Dashboard](docs/portfolio_4/figures/dashboard_advanced.png)

## Weiterführende Ideen

- Indizes/Materialized Views für häufige Reports
- Automatisierte Dashboards in `grafana/provisioning/dashboards`
- Deduplizierung & Historisierung weiterer Entitäten
