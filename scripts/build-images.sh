#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${VTF_REGISTRY:-harbor.viloforge.com/vafi}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Building vtf"
docker build \
    -f "${REPO_ROOT}/Dockerfile.prod" \
    -t "${REGISTRY}/vtf:latest" \
    "${REPO_ROOT}"

echo "==> Done"
docker images | grep vtf
