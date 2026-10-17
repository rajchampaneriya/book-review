#!/usr/bin/env bash
# make observe-up: installs the opt-in OpenTelemetry overlay (collectors,
# lgtm backend, provisioned dashboard). Off for measured runs (D2): the
# stack Deployments are untouched and export nothing unless the overlay's
# OTEL settings are switched on.
set -euo pipefail

cd "$(dirname "$0")/../.."

kubectl apply -f infra/observability/otel-agent.yaml
kubectl apply -f infra/observability/otel-cluster.yaml
# the dashboard ConfigMap is rendered from the tree-listed JSON file
kubectl create configmap wcf-physics-dashboards -n wcf-physics \
  --from-file=wcf-physics-overview.json=infra/observability/dashboards/wcf-physics-overview.json \
  --dry-run=client -o yaml | kubectl apply -n wcf-physics -f -
kubectl apply -f infra/observability/lgtm.yaml

echo "observe-up: waiting for lgtm readiness"
kubectl wait --for=condition=available deploy/lgtm -n wcf-physics --timeout=300s
# ConfigMap changes do not restart pods by themselves
kubectl rollout restart daemonset/otel-agent deploy/otel-cluster -n wcf-physics
kubectl rollout status daemonset/otel-agent -n wcf-physics --timeout=180s
kubectl rollout status deploy/otel-cluster -n wcf-physics --timeout=180s
echo "observe-up: Grafana on http://localhost:8091 (NodePort 30091)"
