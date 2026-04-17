#!/usr/bin/env bash
# launch_ui.sh — run the Stars Reborn reference UI
# Usage: ./launch_ui.sh [args...]
#   -v / --verbose    enable verbose logging
#   --engine-url URL  engine base URL (default: http://localhost:2001)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

# Prefer a local virtualenv if present
if [[ -f ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "error: python3 not found" >&2
    exit 1
fi

exec "$PYTHON" -m src "$@"
