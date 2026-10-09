#!/usr/bin/env bash
# usage: scale.sh <dotnet|java|python> <replicas> (the matrix scales the stacks
# that are not under test to 0).
set -euo pipefail

stack="${1:?usage: scale.sh <dotnet|java|python> <replicas>}"
replicas="${2:?usage: scale.sh <dotnet|java|python> <replicas>}"

kubectl -n wcf-physics scale deploy/"$stack" --replicas="$replicas"
echo "scale: $stack -> $replicas"
