#!/usr/bin/env bash
#
# Run Phase 4 E2E tests: vtf web + vafi-console integration.
#
# Sets up port-forwards for both vtf-api and vafi-console,
# runs Playwright tests, tears down.
#
# Usage: ./e2e/run-e2e.sh

set -euo pipefail

VTF_NS="vtf-dev"
CONSOLE_NS="vafi-dev"
VTF_PORT=9999
CONSOLE_PORT=8765
PIDS=()

cleanup() {
    echo "Stopping port-forwards..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Phase 4 E2E Tests: vtf web + vafi-console ==="
echo ""

# Check cluster access
echo "Checking k8s access..."
kubectl get ns "$VTF_NS" &>/dev/null || { echo "ERROR: Cannot access $VTF_NS namespace"; exit 1; }
kubectl get ns "$CONSOLE_NS" &>/dev/null || { echo "ERROR: Cannot access $CONSOLE_NS namespace"; exit 1; }

# Start port-forwards
echo "Starting vtf-api port-forward ($VTF_PORT)..."
kubectl port-forward -n "$VTF_NS" svc/vtf-api "$VTF_PORT:8000" &>/dev/null &
PIDS+=($!)

echo "Starting vafi-console port-forward ($CONSOLE_PORT)..."
kubectl port-forward -n "$CONSOLE_NS" svc/vafi-console "$CONSOLE_PORT:8080" &>/dev/null &
PIDS+=($!)

# Wait for both to be ready
echo "Waiting for services..."
for i in $(seq 1 20); do
    VTF_OK=$(curl -sf "http://localhost:$VTF_PORT/v1/health" &>/dev/null && echo 1 || echo 0)
    CONSOLE_OK=$(curl -sf "http://localhost:$CONSOLE_PORT/healthz" &>/dev/null && echo 1 || echo 0)
    if [[ "$VTF_OK" == "1" && "$CONSOLE_OK" == "1" ]]; then
        echo "Both services ready."
        break
    fi
    sleep 1
done

if ! curl -sf "http://localhost:$VTF_PORT/v1/health" &>/dev/null; then
    echo "ERROR: vtf-api not reachable at localhost:$VTF_PORT"
    exit 1
fi
if ! curl -sf "http://localhost:$CONSOLE_PORT/healthz" &>/dev/null; then
    echo "ERROR: vafi-console not reachable at localhost:$CONSOLE_PORT"
    exit 1
fi

# Run Playwright tests
echo ""
echo "Running Playwright E2E tests..."
echo "========================================"

cd "$(dirname "$0")/.."

VTF_BASE_URL="http://localhost:$VTF_PORT" \
CONSOLE_BASE_URL="http://localhost:$CONSOLE_PORT" \
npx playwright test e2e/console-widget.spec.ts "$@"
EXIT_CODE=$?

echo "========================================"
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "E2E tests PASSED"
else
    echo "E2E tests FAILED (exit code $EXIT_CODE)"
fi

exit $EXIT_CODE
