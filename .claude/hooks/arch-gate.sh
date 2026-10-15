#!/usr/bin/env bash
# Stop hook: the whole repository must satisfy tools/arch/check_hexagonal.py --all
# (no files outside the CLAUDE.md tree, hexagonal layers and naming for every stack
# that exists) before a turn may finish. Exit 2 blocks the finish and feeds the
# violations back; fix the code, never the check.
set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

PYTHON="$PROJECT_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python3

out=$(cd "$PROJECT_DIR" && "$PYTHON" -B tools/arch/check_hexagonal.py --all 2>&1)
status=$?

if [ $status -eq 0 ]; then
  exit 0
fi

echo "arch-gate: check_hexagonal.py --all failed (fix the code, never the check):" >&2
printf '%s\n' "$out" >&2
exit 2
