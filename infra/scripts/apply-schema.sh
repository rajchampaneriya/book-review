#!/usr/bin/env bash
# Render db/schema.sql once per stack schema and apply it inside the Postgres pod.
set -euo pipefail

cd "$(dirname "$0")/../.."

for stack in dotnet java python; do
  sed "s/{stack}/$stack/g" db/schema.sql \
    | kubectl exec -n wcf-physics -i deploy/postgres -- psql -v ON_ERROR_STOP=1 -U wcf -d bookings \
    >/dev/null
  echo "schema: applied for '$stack'"
done
