#!/usr/bin/env bash
# Generate a throwaway app from template-web and assert the api half is sane.
set -euo pipefail

OS="$HOME/systems/os"
TMP="$(mktemp -d /tmp/sx-template.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

copier copy --trust --defaults \
  --data app_name="Regression Demo" \
  --data app_slug="regression-demo" \
  --data pitch="engine self-test" \
  --data sconixapp_path="$OS/sconixapp" \
  --data created_at="$(date -Idate)" \
  "$OS/template-web" "$TMP/regression-demo"

cd "$TMP/regression-demo"
echo ":: generated -> $PWD"
test -f api/pyproject.toml
test -f web/package.json
test -f docker-compose.yml
test -f Caddyfile
! grep -rq '{{' api web packages || { echo "unrendered jinja left in output"; exit 1; }

TMPDIR=/tmp uv sync --project api
uv run --project api ruff check api
TMPDIR=/tmp uv run --project api pytest api

echo ":: template api OK"
