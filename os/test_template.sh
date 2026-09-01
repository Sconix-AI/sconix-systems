#!/usr/bin/env bash
# Generate a throwaway app from template-web and assert both halves are sane.
# Set SKIP_WEB=1 to skip the (slower) pnpm install + next build.
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
test -f Caddyfile.site
test -f sconix.yaml
grep -q '__API_UPSTREAM__' Caddyfile.site
grep -q 'SCONIX_SLOT' docker-compose.yml
# leaked Jinja looks like `{{ var }}` / `{% ... %}` / `{# ... #}`; JSX inline
# objects (`={{`, `{{ ... }}` without a bare identifier) are fine.
! grep -rnE '\{\{ [a-z_]+ \}\}|\{%[-+ ]|\{#' api web packages \
  || { echo "unrendered jinja left in output"; exit 1; }

test -f web/lib/config.ts        # config.ts.jinja must have rendered
"$OS/sconixcore/.venv/bin/sconix-inspect" . --strict --json >/dev/null

TMPDIR=/tmp uv sync --project api
uv run --project api ruff check api
TMPDIR=/tmp uv run --project api pytest api
echo ":: template api OK"

if [ "${SKIP_WEB:-}" != "1" ]; then
  TMPDIR=/tmp pnpm install --silent
  TMPDIR=/tmp pnpm --filter web build
  echo ":: template web OK"
fi
