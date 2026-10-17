#!/usr/bin/env bash
# make observe-up: installs the opt-in OpenTelemetry overlay (collectors,
# lgtm backend, provisioned dashboard) and switches the stacks' telemetry
# on. Off for measured runs (D2): infra/k8s/<stack>.yaml sets
# OTEL_SDK_DISABLED=true, so `make up` or `kubectl apply -f
# infra/k8s/<stack>.yaml` turns a stack's telemetry off again.
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

# Step 5: the stacks export traces and metrics to the node collector.
# java: the OpenTelemetry agent ships in the image and loads only when
# JAVA_TOOL_OPTIONS names it; its logs stay local, as in the other stacks.
# One stack at a time: each rollout briefly runs a second 1Gi pod, and the
# single k3d node has room for one such surge, not three (FailedScheduling:
# Insufficient memory, 2026-10-17).
otlp="http://otel-agent.wcf-physics.svc:4317"
for stack in python java dotnet; do
  extra=()
  if [ "$stack" = java ]; then
    extra=(JAVA_TOOL_OPTIONS=-javaagent:/otel/opentelemetry-javaagent.jar OTEL_LOGS_EXPORTER=none)
  fi
  echo "observe-up: telemetry on for $stack"
  kubectl -n wcf-physics set env deploy/"$stack" \
    OTEL_SDK_DISABLED=false OTEL_SERVICE_NAME="$stack" \
    OTEL_EXPORTER_OTLP_ENDPOINT="$otlp" OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
    OTEL_METRIC_EXPORT_INTERVAL=15000 \
    ${extra[@]+"${extra[@]}"}  # bash 3.2 (macOS) and set -u safe
  kubectl -n wcf-physics rollout status deploy/"$stack" --timeout=180s
done
echo "observe-up: Grafana on http://localhost:8091 (NodePort 30091)"
