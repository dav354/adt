#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:-backups}"
mkdir -p "$output_dir"

timestamp="$(date +%Y%m%d-%H%M%S)"
outfile="${output_dir}/lobbyregister_dump_${timestamp}.dump"

if [[ -f ".env" ]]; then
    # shellcheck disable=SC2046
    export $(grep -E '^(POSTGRES_(USER|PASSWORD|DB|HOST|PORT))=' .env | xargs)
fi

pg_user="${POSTGRES_USER}"
pg_password="${POSTGRES_PASSWORD}"
pg_db="${POSTGRES_DB}"
pg_host="${POSTGRES_HOST:-db}"
pg_port="${POSTGRES_PORT:-5432}"

if [[ -z "${pg_user}" || -z "${pg_password}" || -z "${pg_db}" ]]; then
    echo "POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB must be set" >&2
    exit 1
fi

pg_dump --format=custom --file "${outfile}" \
    "postgresql://${pg_user}:${pg_password}@${pg_host}:${pg_port}/${pg_db}"

echo "Database dump written to ${outfile}"
