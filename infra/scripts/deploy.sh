#!/usr/bin/env bash
# make deploy STACK=<stack>: build the runtime image, import it into k3d, roll it out.
set -euo pipefail

cd "$(dirname "$0")/../.."
ENGINE="${ENGINE:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}"
stack="${1:?usage: deploy.sh <dotnet|java|python>}"

"$ENGINE" build --target runtime -t "wcf-physics/$stack:dev" "stacks/$stack"
k3d image import "wcf-physics/$stack:dev" -c wcf-physics
kubectl -n wcf-physics scale deploy/"$stack" --replicas=1
kubectl -n wcf-physics rollout restart deploy/"$stack"
kubectl -n wcf-physics rollout status deploy/"$stack" --timeout=180s
echo "deploy: $stack rolled out (wcf-physics/$stack:dev)"
