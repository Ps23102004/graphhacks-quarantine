#!/usr/bin/env bash
# Working-tree validation (not a fresh clone).
#   scripts/validate.sh
# Copies the working tree, uncommitted edits included (.git/.venv excluded): run it on a clean tree to validate a commit.
# Starts a throwaway FalkorDB on port 6390, runs tests, demo commands, MCP bridge, and web.
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash on Windows would rewrite container paths
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) KILLEXIT=1;; *) KILLEXIT=-9;; esac   # a killed process exits 1 on Windows, -9 elsewhere

IMAGE="falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6"
NAME="quarantine-validate"
PORT=6390
WEB=8791
SRC="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
pass=0; fail=0
ok()   { echo "  PASS  $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL  $1"; fail=$((fail+1)); }
skip() { echo "  SKIP  $1"; }
has()  { grep -qF -- "$2" <<<"$1" && ok "$3" || bad "$3  (missing: $2)"; }
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; [ -n "${WEBPID:-}" ] && kill "$WEBPID" 2>/dev/null || true; rm -rf "$WORK"; }
trap cleanup EXIT

mkdir -p "$WORK/repo"
if [ -z "$(git -C "$SRC" status --porcelain)" ]; then
  echo "== working tree is clean; copying working tree =="
else
  echo "== working tree has uncommitted edits; explicitly testing working tree (not stale HEAD) =="
fi

# Copy working tree (including uncommitted edits) excluding transient caches
tar -C "$SRC" --exclude='.git' --exclude='.venv' --exclude='.pytest_cache' --exclude='dist' --exclude='build' -cf - . | tar -C "$WORK/repo" -xf -
cd "$WORK/repo"

echo "== throwaway FalkorDB on :$PORT"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "$PORT:6379" "$IMAGE" >/dev/null
for i in $(seq 1 30); do docker exec "$NAME" redis-cli ping 2>/dev/null | grep -q PONG && break; sleep 1; done
docker exec "$NAME" redis-cli ping | grep -q PONG && ok "FalkorDB up" || { bad "FalkorDB did not start"; exit 1; }
export FALKORDB_PORT="$PORT"

echo "== install dependencies and sync lockfile"
uv sync --frozen --all-extras -q && ok "uv sync --frozen --all-extras" || { bad "uv sync"; exit 1; }

echo "== run tests"
out="$(uv run pytest -q 2>&1)" && ok "pytest: $(tail -1 <<<"$out")" || { bad "pytest"; echo "$out" | tail -20; }

echo "== demo commands (graph 'validate')"
out="$(uv run quarantine session1 --graph validate)"
has "$out" "25 memories written" "session1 writes 25 memories"
has "$out" "session 1 done - 0 processes running" "session1 ends with 0 processes"
has "$out" "read [step_3, step_1] -> wrote a_requirements" "read set printed before the write"

out="$(uv run quarantine flag doc_7 --graph validate)"
has "$out" "quarantined 6 | wipe agents 25 | roll back 19" "flag: 6 vs 25 vs 19"
has "$out" "closure [ep_7a, ep_7b, f_http_client, f_http_pin, step_3, a_requirements]" "flag: the six memories"
has "$out" "receipt a_requirements (4 hops)" "flag: 4-hop receipt"

out="$(uv run quarantine session2 --graph validate)"
has "$out" "fixpoint: rounds [1, 2, 2, 0], 28 memories" "session2: fixpoint rounds"
has "$out" "healed f_http_client -> f_http_client_v2 = requests" "session2: heals the package fact"
case "$out" in *"healed f_http_pin"*) bad "session2 must not heal the version pin (one bad source)";; *) ok "session2 leaves the version pin red";; esac

uv run quarantine session1 --graph validate >/dev/null
uv run quarantine flag doc_7 --graph validate >/dev/null
out="$(uv run quarantine session2 --kill-planner --graph validate)"
has "$out" "kill -9, exit $KILLEXIT" "kill-planner: the planner process is really killed (exit $KILLEXIT here)"
has "$out" "claim refused at tick" "kill-planner: live lease refuses a second claim"
has "$out" "took over lease from planner" "kill-planner: session s2b takes over expired lease"
has "$out" "rounds [1, 2, 2, 0]" "kill-planner: same fixpoint"

echo "== control: a different doc gives a different, hand-derived closure"
uv run quarantine session1 --graph validate_ctl >/dev/null
out="$(uv run quarantine flag doc_5 --graph validate_ctl)"
has "$out" "closure [ep_5, f_http_client, step_3, a_requirements]" "flag doc_5: ep_5 -> f_http_client -> step_3 -> a_requirements"
has "$out" "quarantined 4 " "flag doc_5: quarantined 4"

echo "== packaging and wheel build"
uv build --wheel -q && ok "uv build --wheel" || bad "uv build failed"

echo "== MCP inspection bridge"
mcp_list="$(QUARANTINE_GRAPH=validate uv run scripts/mcp_inspect.py list 2>&1)"
has "$mcp_list" "inspect_quarantined_memories" "mcp list: inspect_quarantined_memories"
has "$mcp_list" "trace_provenance_receipt" "mcp list: trace_provenance_receipt"
has "$mcp_list" "get_recovery_status" "mcp list: get_recovery_status"

mcp_call="$(QUARANTINE_GRAPH=validate uv run scripts/mcp_inspect.py call trace_provenance_receipt '{"memory_id": "a_requirements"}' 2>&1)"
has "$mcp_call" "hops" "mcp call trace_provenance_receipt returns hops"

echo "== Compose configuration"
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  docker compose -f deploy/docker-compose.yml config --quiet && ok "docker compose config valid" || bad "docker compose config invalid"
else
  skip "docker compose CLI not found"
fi

echo "== web page"
uv run python web/server.py --port "$WEB" --graph validate >/dev/null 2>&1 &
WEBPID=$!
for i in $(seq 1 20); do curl -s -o /dev/null "localhost:$WEB/graph" && break; sleep 1; done
g="$(curl -s "localhost:$WEB/graph" || true)"
has "$g" '"precise": 6' "page JSON: precise 6"
has "$g" '"per_agent": 25' "page JSON: per_agent 25 after healing"
has "$g" '"time_based": 19' "page JSON: time_based 19 after healing"
[ "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: evil.example' "localhost:$WEB/graph")" = 403 ] && ok "page refuses foreign Host" || bad "page Host check"
[ "$(curl -s -o /dev/null -w '%{http_code}' -X POST "localhost:$WEB/graph")" = 405 ] && ok "page refuses POST method" || bad "page POST check"

echo
echo "validation: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
