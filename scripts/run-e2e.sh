#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose.e2e.yml"
PROJECT="vtf-e2e"

cleanup() {
    echo "Tearing down E2E stack..."
    docker compose -f "$COMPOSE_FILE" -p "$PROJECT" down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "Building and starting E2E stack..."
docker compose -f "$COMPOSE_FILE" -p "$PROJECT" up -d --build --wait

echo "Running migrations..."
docker compose -f "$COMPOSE_FILE" -p "$PROJECT" exec -T api python src/manage.py migrate --run-syncdb

echo "Seeding test data..."
docker compose -f "$COMPOSE_FILE" -p "$PROJECT" exec -T api python -c "exec(open('/app/tests/e2e/seed.py').read())"

echo "Waiting for MCP server..."
for i in $(seq 1 30); do
    if python3 -c "import httpx; httpx.get('http://localhost:18002/', timeout=2)" 2>/dev/null; then
        echo "MCP server ready."
        break
    fi
    sleep 1
done

echo "Running E2E tests..."
pytest tests/e2e/ -v --tb=short
exit_code=$?

echo "E2E tests finished with exit code $exit_code"
exit $exit_code
