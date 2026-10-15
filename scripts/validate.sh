#!/usr/bin/env bash
# Fresh-clone validation: what a judge (or Aman, or a clean machine) would do.
#   scripts/validate.sh            validates the committed HEAD of this repo
# Starts a throwaway FalkorDB (same pinned image) on port 6390, clones HEAD into a temp dir,
# installs from the lockfile, and checks every number the video says. Exit 0 = all green.
set -euo pipefail

IMAGE="falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6"
NAME="quarantine-validate"
PORT=6390
WEB=8791
SRC="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
pass=0; fail=0
ok()   { echo "  PASS  $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL  $1"; fail=$((fail+1)); }
has()  { grep -qF -- "$2" <<<"$1" && ok "$3" || bad "$3  (missing: $2)"; }
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; [ -n "${WEBPID:-}" ] && kill "$WEBPID" 2>/dev/null || true; rm -rf "$WORK"; }
trap cleanup EXIT

[ -z "$(git -C "$SRC" status --porcelain)" ] || echo "  note: working tree is dirty; validating committed HEAD only"
echo "== clone HEAD $(git -C "$SRC" rev-parse --short HEAD)"
git clone -q "$SRC" "$WORK/repo"
cd "$WORK/repo"

echo "== throwaway FalkorDB on :$PORT"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "$PORT:6379" "$IMAGE" >/dev/null
for i in $(seq 1 30); do docker exec "$NAME" redis-cli ping 2>/dev/null | grep -q PONG && break; sleep 1; done
docker exec "$NAME" redis-cli ping | grep -q PONG && ok "FalkorDB up" || { bad "FalkorDB did not start"; exit 1; }
export FALKORDB_PORT="$PORT"

echo "== install from lockfile"
uv sync --frozen -q && ok "uv sync --frozen" || { bad "uv sync"; exit 1; }

echo "== tests"
out="$(uv run pytest -q 2>&1)" && ok "pytest: $(tail -1 <<<"$out")" || { bad "pytest"; echo "$out" | tail -20; }

echo "== demo commands (graph 'validate')"
out="$(uv run quarantine session1 --graph validate)"
has "$out" "25 memories written" "session1 writes 25 memories"
has "$out" "session 1 done - 0 processes running" "session1 ends with 0 processes"
has "$out" "read [step_3, step_1] -> wrote a_requirements" "read set printed before the write"

out="$(uv run quarantine flag doc_7 --graph validate)"
has "$out" "precise 6 | per-agent 25 | time-based 19" "flag: 6 vs 25 vs 19"
has "$out" "closure [ep_7a, ep_7b, f_http_client, f_http_pin, step_3, a_requirements]" "flag: the six memories"
has "$out" "receipt a_requirements (4 hops)" "flag: 4-hop receipt"

out="$(uv run quarantine session2 --graph validate)"
has "$out" "fixpoint: rounds [1, 2, 2, 0], 28 memories" "session2: fixpoint rounds"
has "$out" "healed f_http_client -> f_http_client_v2 = requests" "session2: heals the package fact"
case "$out" in *"healed f_http_pin"*) bad "session2 must not heal the version pin (one bad source)";; *) ok "session2 leaves the version pin red";; esac

uv run quarantine session1 --graph validate >/dev/null
uv run quarantine flag doc_7 --graph validate >/dev/null
out="$(uv run quarantine session2 --kill-planner --graph validate)"
has "$out" "kill -9, exit -9" "kill-planner: the planner process is really SIGKILLed"
has "$out" "claim refused at tick" "kill-planner: live lease refuses a second claim"
has "$out" "took over lease from planner" "kill-planner: new process takes over expired lease"
has "$out" "rounds [1, 2, 2, 0]" "kill-planner: same fixpoint"

echo "== control: a different doc gives a different, hand-derived closure"
uv run quarantine session1 --graph validate_ctl >/dev/null
out="$(uv run quarantine flag doc_5 --graph validate_ctl)"
has "$out" "closure [ep_5, f_http_client, step_3, a_requirements]" "flag doc_5: ep_5 -> f_http_client -> step_3 -> a_requirements"
has "$out" "precise 4 " "flag doc_5: precise 4"

echo "== page"
uv run python web/server.py --port "$WEB" --graph validate >/dev/null 2>&1 &
WEBPID=$!
for i in $(seq 1 20); do curl -s -o /dev/null "localhost:$WEB/graph" && break; sleep 1; done
g="$(curl -s "localhost:$WEB/graph" || true)"
has "$g" '"precise": 6' "page JSON: precise 6"
has "$g" '"per_agent": 25' "page JSON: per_agent 25 after healing"
has "$g" '"time_based": 19' "page JSON: time_based 19 after healing"
[ "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: evil.example' "localhost:$WEB/graph")" = 403 ] && ok "page refuses foreign Host" || bad "page Host check"

echo
echo "validation: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
