#!/usr/bin/env bash
# make doctor: check host prerequisites and build the host .venv.
# The host runs only the hooks, tools/arch, the contract tests, the harness
# and the chart; no JDK, .NET SDK or Python 3.14 needed on the host itself.
set -euo pipefail

cd "$(dirname "$0")/../.."

fail=0
need() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "ok      $1 $($2 2>/dev/null | head -1)"
  else
    echo "MISSING $1: $3"
    fail=1
  fi
}

ENGINE=""
if command -v docker >/dev/null 2>&1; then
  ENGINE=docker
elif command -v podman >/dev/null 2>&1; then
  ENGINE=podman
else
  echo "MISSING container engine: install Docker Desktop or Podman"
  fail=1
fi
if [ -n "$ENGINE" ]; then
  echo "ok      $ENGINE ($("$ENGINE" --version | head -1))"
  "$ENGINE" info >/dev/null 2>&1 || { echo "NOT RUNNING: $ENGINE daemon is unreachable"; fail=1; }
fi

need k3d 'k3d version' 'brew install k3d'
need kubectl 'kubectl version --client' 'brew install kubectl'
need k6 'k6 version' 'brew install k6'
need jq 'jq --version' 'brew install jq'

if command -v python3 >/dev/null 2>&1; then
  py=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
    && echo "ok      python3 $py" \
    || { echo "TOO OLD  python3 $py (3.12 or later required)"; fail=1; }
else
  echo "MISSING python3 (3.12 or later)"
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
  fi
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements-host.txt
  echo "ok      .venv (.venv/bin/pytest $(.venv/bin/pytest --version | awk '{print $2}'))"
  echo "doctor: all prerequisites present"
else
  echo "doctor: fix the missing tools above and re-run"
  exit 1
fi
