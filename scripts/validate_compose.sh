#!/usr/bin/env bash
set -euo pipefail

PROJECT="quarantine_compose_test_$$"
PORT=8777
SRC="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
  echo "Cleaning up Compose project: $PROJECT"
  docker compose -p "$PROJECT" -f "$SRC/deploy/docker-compose.yml" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== 1. Validate Compose config =="
docker compose -f "$SRC/deploy/docker-compose.yml" config --quiet

echo "== 2. Build and launch Compose project on port $PORT =="
WEB_PORT="$PORT" docker compose -p "$PROJECT" -f "$SRC/deploy/docker-compose.yml" up --build -d

echo "== 3. Wait for services to be ready =="
for i in $(seq 1 30); do
  if curl -s -f "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    echo "Web service is responding on 127.0.0.1:$PORT"
    break
  fi
  sleep 1
done

echo "== 4. Seed test graph in Compose =="
# Seed via Python passing host explicitly so it works regardless of whether Core has completed Finding 4
docker compose -p "$PROJECT" -f "$SRC/deploy/docker-compose.yml" exec -T web \
  /app/.venv/bin/python -c "
import os
from quarantine.loader import connect, load, read_fixture
host = os.environ.get('FALKORDB_HOST', 'falkordb')
g = connect('quarantine', host=host)
load(g, read_fixture())
print('Seeded graph quarantine on host', host)
"

echo "== 5. Verify HTTP endpoints =="
# Check root page
curl -s -f "http://127.0.0.1:$PORT/" | grep -q "QUARANTINE"
echo "  PASS: GET /"

# Check vendor js
curl -s -f -o /dev/null "http://127.0.0.1:$PORT/vendor/vis-network.min.js"
echo "  PASS: GET /vendor/vis-network.min.js"

# Check /graph JSON
out="$(curl -s -f "http://127.0.0.1:$PORT/graph")"
grep -q '"nodes"' <<<"$out"
echo "  PASS: GET /graph returns snapshot"

# Check Host allowlist acceptance
code="$(curl -s -o /dev/null -w '%{http_code}' -H "Host: web:8765" "http://127.0.0.1:$PORT/graph")"
[ "$code" = "200" ]
echo "  PASS: Allowed Host header returns 200"

# Check Host allowlist rejection
code="$(curl -s -o /dev/null -w '%{http_code}' -H "Host: malicious.example" "http://127.0.0.1:$PORT/graph")"
[ "$code" = "403" ]
echo "  PASS: Malicious Host header returns 403"

# Check method not allowed
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/graph")"
[ "$code" = "405" ]
echo "  PASS: POST /graph returns 405"

# Check 404
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/not_found_test")"
[ "$code" = "404" ]
echo "  PASS: Unknown route returns 404"

echo "== 6. Test persistence across container recreation =="
# Stop and remove containers without removing volume
docker compose -p "$PROJECT" -f "$SRC/deploy/docker-compose.yml" stop
docker compose -p "$PROJECT" -f "$SRC/deploy/docker-compose.yml" rm -f

# Bring containers back up with existing volume
WEB_PORT="$PORT" docker compose -p "$PROJECT" -f "$SRC/deploy/docker-compose.yml" up -d

for i in $(seq 1 30); do
  if curl -s -f "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Verify data persisted
reloaded="$(curl -s -f "http://127.0.0.1:$PORT/graph")"
grep -q '"nodes"' <<<"$reloaded"
if grep -q 'a_requirements' <<<"$reloaded"; then
  echo "  PASS: Graph data persisted across container recreate!"
else
  echo "  FAIL: Data lost across container recreate"
  exit 1
fi

echo "Compose validation complete: ALL PASS"
