#!/usr/bin/env bash
set -eo pipefail

# Verzeichnisse
DOCS_DIR="docs/benchmark_results"
mkdir -p "$DOCS_DIR"

echo ""
echo "#########################################################"
echo "#  🚀 LOBBYREGISTER PERFORMANCE MESSUNG (Cold vs Warm)  #"
echo "#########################################################"
echo ""

# ---------------------------------------------------------
# PHASE 1: UNOPTIMIZED (Baseline)
# ---------------------------------------------------------
echo ">> [1/4] Bereite Baseline vor (Lösche Optimierungen)..."
# Wir löschen sicherheitshalber alle neuen Views/MVs (vw_/mv_) und idx_-Indizes aus optimization.sql
docker compose exec db psql -U test -d lobby -c "
DO \$\$DECLARE r record;
BEGIN
  -- Drop plain views (vw_*)
  FOR r IN SELECT schemaname, viewname FROM pg_views WHERE schemaname = 'public' AND viewname LIKE 'vw_%'
  LOOP EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE;', r.schemaname, r.viewname); END LOOP;

  -- Drop materialized views (mv_*)
  FOR r IN SELECT schemaname, matviewname AS viewname FROM pg_matviews WHERE schemaname = 'public' AND matviewname LIKE 'mv_%'
  LOOP EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I.%I CASCADE;', r.schemaname, r.viewname); END LOOP;

  -- Drop optimization indexes (idx_*)
  FOR r IN SELECT schemaname, indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%'
  LOOP EXECUTE format('DROP INDEX IF EXISTS %I.%I;', r.schemaname, r.indexname); END LOOP;

  -- Drop trigram extension if present
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    EXECUTE 'DROP EXTENSION IF EXISTS pg_trgm CASCADE';
  END IF;
END\$\$;
" > /dev/null 2>&1

echo ">> Restarting DB to clear Cache (Cold State)..."
docker compose restart db
# Wir warten, bis die DB wirklich wieder da ist
sleep 5
until docker compose exec db pg_isready -U test > /dev/null 2>&1; do
  echo "   ...waiting for DB..."
  sleep 2
done

echo ">> Running Benchmark: UNOPTIMIZED (COLD)..."
uv run python benchmark.py "$DOCS_DIR/1_baseline_cold.md"

echo ">> Running Benchmark: UNOPTIMIZED (WARM)..."
# Direkt hinterher, Daten sind jetzt im RAM
uv run python benchmark.py "$DOCS_DIR/2_baseline_warm.md"


# ---------------------------------------------------------
# PHASE 2: OPTIMIZED
# ---------------------------------------------------------
echo ""
echo ">> [2/4] Wende Optimierungen an (optimization.sql)..."
# Wir lesen die optimization.sql ein und führen sie im Container aus
# Hinweis: Wir nutzen 'cat' und pipe, um Pfadprobleme im Container zu vermeiden
cat ../src/lobbyregister_ingestor/optimization.sql | docker compose exec -T db psql -U test -d lobby > /dev/null

# Refresh MVs to ensure data is populated
echo ">> Refreshing Materialized Views..."
docker compose exec db psql -U test -d lobby -c "
    REFRESH MATERIALIZED VIEW public.mv_financial_tops;
    REFRESH MATERIALIZED VIEW public.mv_revolving_door_network;
" > /dev/null

echo ">> Restarting DB to clear Cache (Optimized Cold State)..."
docker compose restart db
sleep 5
until docker compose exec db pg_isready -U test > /dev/null 2>&1; do
  echo "   ...waiting for DB..."
  sleep 2
done

echo ">> Running Benchmark: OPTIMIZED (COLD)..."
uv run python benchmark.py "$DOCS_DIR/3_optimized_cold.md"

echo ">> Running Benchmark: OPTIMIZED (WARM)..."
uv run python benchmark.py "$DOCS_DIR/4_optimized_warm.md"

echo ""
echo "#########################################################"
echo "✅ Fertig! Berichte liegen in $DOCS_DIR"
echo "#########################################################"
ls -l $DOCS_DIR
