#!/usr/bin/env bash
# make down: delete the k3d cluster (Postgres storage is disposable by design).
set -euo pipefail

k3d cluster delete wcf-physics
echo "down: cluster deleted"
