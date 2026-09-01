#!/usr/bin/env bash
set -euo pipefail

OS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

for tool in git uv; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 1; }
done

if ! command -v copier >/dev/null; then
  echo ":: installing copier"
  uv tool install copier
fi

echo ":: installing sconixcore from $OS/sconixcore"
TMPDIR=/tmp uv sync --project "$OS/sconixcore"

mkdir -p "$HOME/bin"
ln -sfn "$OS/bin/sx" "$HOME/bin/sx"

echo "Sconix installed. Add $HOME/bin to PATH if needed."
echo "Try: sx new demo --no-gh"
