#!/usr/bin/env bash
# make up: k3d cluster, Postgres, per-stack schemas, all stack manifests.
set -euo pipefail

cd "$(dirname "$0")/../.."
ENGINE="${ENGINE:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}"

if k3d cluster get wcf-physics >/dev/null 2>&1; then
  echo "up: cluster wcf-physics already exists"
else
  k3d cluster create -c infra/k3d/cluster.yaml
fi

kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/rbac.yaml
kubectl apply -f infra/k8s/network-policy.yaml
kubectl apply -f infra/k8s/postgres.yaml
echo "up: waiting for Postgres readiness"
kubectl wait --for=condition=available deploy/postgres -n wcf-physics --timeout=180s

bash infra/scripts/apply-schema.sh

# after the schemas exist, so the first scheduled audit finds the tables
kubectl apply -f infra/k8s/duplicate-audit.yaml

kubectl apply -f infra/k8s/dotnet.yaml -f infra/k8s/java.yaml -f infra/k8s/python.yaml
echo "up: applied all stack manifests (dotnet and java images arrive in P2; scale them to 0 until then)"
kubectl -n wcf-physics scale deploy/dotnet deploy/java --replicas=0
echo "up: done"
