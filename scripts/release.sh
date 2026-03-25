#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/release.sh <env>
#   env: dev or prod
#
# Steps:
#   1. Build production image from Dockerfile.prod
#   2. Tag with git SHA + "latest"
#   3. Push to Harbor
#   4. Apply k8s manifests to target namespace
#   5. Run migrations
#   6. Wait for rollout
#   7. Health check

REGISTRY="harbor.viloforge.com/vafi/vtf"
KUBECONFIG="${KUBECONFIG:-$HOME/.kube/vafi-dev.yaml}"
export KUBECONFIG

ENV="${1:-}"
if [[ -z "$ENV" || ! "$ENV" =~ ^(dev|prod)$ ]]; then
    echo "Usage: $0 <dev|prod>"
    exit 1
fi

# Resolve environment settings
case "$ENV" in
    dev)
        NAMESPACE="vtf-dev"
        OVERLAY="k8s/overlays/dev"
        API_HOST="vtf.dev.viloforge.com"
        MCP_HOST="vtf-mcp.dev.viloforge.com"
        ;;
    prod)
        NAMESPACE="vtf-prod"
        OVERLAY="k8s/overlays/prod"
        API_HOST="vtf.viloforge.com"
        MCP_HOST="vtf-mcp.viloforge.com"
        ;;
esac

GIT_SHA=$(git rev-parse --short HEAD)
IMAGE_TAG="${REGISTRY}:${GIT_SHA}"
IMAGE_LATEST="${REGISTRY}:latest"

echo "=== Release to ${ENV} ==="
echo "  Image:     ${IMAGE_TAG}"
echo "  Namespace: ${NAMESPACE}"
echo "  Overlay:   ${OVERLAY}"
echo "  API:       https://${API_HOST}"
echo "  MCP:       https://${MCP_HOST}"
echo ""

# Step 1: Build
echo "Building production image..."
docker build -f Dockerfile.prod -t "${IMAGE_TAG}" -t "${IMAGE_LATEST}" .

# Step 2: Push
echo "Pushing to Harbor..."
docker push "${IMAGE_TAG}"
docker push "${IMAGE_LATEST}"

# Step 3: Update kustomization with the SHA tag
echo "Updating image tag in overlay to ${GIT_SHA}..."
sed -i "s|newTag:.*|newTag: ${GIT_SHA}|" "${OVERLAY}/kustomization.yaml"

# Step 4: Apply manifests
echo "Applying manifests to ${NAMESPACE}..."
kubectl create namespace "${NAMESPACE}" 2>/dev/null || true
kubectl apply -k "${OVERLAY}"

# Step 5: Wait for migration job
echo "Running migrations..."
# Delete old migration job if it exists (jobs are immutable)
kubectl delete job vtf-migrate -n "${NAMESPACE}" 2>/dev/null || true
kubectl apply -k "${OVERLAY}"  # re-apply to create the job fresh
kubectl wait --for=condition=complete job/vtf-migrate -n "${NAMESPACE}" --timeout=120s

# Step 6: Wait for rollouts
echo "Waiting for rollouts..."
kubectl rollout status deployment/vtf-api -n "${NAMESPACE}" --timeout=120s
kubectl rollout status deployment/vtf-mcp -n "${NAMESPACE}" --timeout=120s
kubectl rollout status deployment/vtf-celery -n "${NAMESPACE}" --timeout=120s
kubectl rollout status deployment/vtf-celery-beat -n "${NAMESPACE}" --timeout=120s

# Step 7: Health checks
echo "Running health checks..."
sleep 5  # wait for ingress to catch up

API_HEALTH=$(curl -sf "https://${API_HOST}/v1/health" 2>&1 || echo "FAILED")
echo "  API health: ${API_HEALTH}"

MCP_HEALTH=$(curl -sf "https://${MCP_HOST}/" 2>&1 || echo "FAILED")
echo "  MCP reachable: $(echo "${MCP_HEALTH}" | head -c 50)"

# Step 8: Report
echo ""
echo "=== Release complete ==="
echo "  Image:  ${IMAGE_TAG}"
echo "  API:    https://${API_HOST}/v1/health"
echo "  MCP:    https://${MCP_HOST}/mcp"
echo ""
echo "Pods:"
kubectl get pods -n "${NAMESPACE}" --no-headers | sed 's/^/  /'
