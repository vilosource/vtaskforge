#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${VTF_REGISTRY:-harbor.viloforge.com/vafi}"

echo "==> Pushing vtf"
docker push "${REGISTRY}/vtf:latest"

echo "==> Done"
