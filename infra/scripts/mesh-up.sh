#!/usr/bin/env bash
# make mesh-up: installs the opt-in Istio ambient overlay (platform plan
# section 3.2, step 6). Off for measured runs (D2): ztunnel, istiod and
# the waypoint add work to every request, so the 54-run matrix runs with
# the cluster as make up leaves it.
# Requires the cluster recreated without Traefik (infra/k3d/cluster.yaml).
set -euo pipefail

cd "$(dirname "$0")/../.."

ISTIO_VERSION="1.31.2"
GATEWAY_API_VERSION="v1.6.0"
ISTIOCTL="${ISTIOCTL:-.venv/bin/istioctl}"

if ! "$ISTIOCTL" version >/dev/null 2>&1; then
  echo "mesh-up: downloading istioctl ${ISTIO_VERSION} into .venv/bin"
  curl -fsSL \
    "https://github.com/istio/istio/releases/download/${ISTIO_VERSION}/istioctl-${ISTIO_VERSION}-osx-arm64.tar.gz" \
    | tar -xz -C .venv/bin istioctl
fi

echo "mesh-up: Gateway API CRDs ${GATEWAY_API_VERSION} (experimental channel: HTTPRoute retries)"
kubectl apply --server-side \
  -f "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/experimental-install.yaml"

echo "mesh-up: Istio ${ISTIO_VERSION} ambient profile (platform k3d)"
# k3s keeps CNI binaries in its own data dir, not /opt/cni/bin.
"$ISTIOCTL" install -y --set profile=ambient \
  --set values.global.platform=k3d \
  --set values.cni.cniBinDir=/var/lib/rancher/k3s/data/cni
kubectl wait --for=condition=available deploy/istiod -n istio-system --timeout=300s
kubectl wait --for=condition=ready pod/-l app=ztunnel -n istio-system --timeout=300s

kubectl label namespace wcf-physics istio.io/dataplane-mode=ambient --overwrite

echo "mesh-up: waypoint for L7 policy on the python Service"
"$ISTIOCTL" x waypoint apply -n wcf-physics
kubectl wait --for=condition=available deploy/waypoint -n wcf-physics --timeout=180s
kubectl annotate service python -n wcf-physics istio.io/use-waypoint='"waypoint"' --overwrite

kubectl apply -f infra/mesh/security.yaml
kubectl apply -f infra/mesh/gateway.yaml
kubectl apply -f infra/mesh/traffic.yaml
kubectl apply -f infra/k8s/network-policy.yaml

kubectl wait --for=condition=available deploy/host-gateway-istio -n wcf-physics --timeout=300s
echo "mesh-up: gateway on http://localhost:8090 (NodePort 30090)"
