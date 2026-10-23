#!/usr/bin/env bash
# Render db/schema.sql once per stack schema and apply it through the
# in-cluster schema-apply Job (platform plan section 3.1): the SQL goes into
# the schema-sql ConfigMap, the Job runs psql against the postgres Service,
# and this script waits for the Job to complete.
set -euo pipefail

cd "$(dirname "$0")/../.."

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

for stack in dotnet java python; do
  # the database is disposable (PVC): re-applying starts from a clean schema
  { echo "DROP SCHEMA IF EXISTS $stack CASCADE;"; sed "s/{stack}/$stack/g" db/schema.sql; } \
    > "$tmp/$stack.sql"
done

kubectl -n wcf-physics create configmap schema-sql --from-file="$tmp" \
  --dry-run=client -o yaml | kubectl apply -f -

# Job specs are immutable: delete the previous run before applying again.
kubectl -n wcf-physics delete job schema-apply --ignore-not-found
kubectl apply -f infra/k8s/schema-job.yaml

kubectl -n wcf-physics wait --for=condition=complete job/schema-apply --timeout=180s
echo "schema: applied for 'dotnet', 'java' and 'python' through the schema-apply Job"
