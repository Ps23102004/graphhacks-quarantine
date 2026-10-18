#!/usr/bin/env bash
# Run the checks in ten different environments: fresh clones of the committed HEAD, three Python versions, each with its
# own throwaway FalkorDB container on its own port. Nothing touches the demo database or your working tree.
#   scripts/env_matrix.sh            # about 10 minutes; prints one PASS/FAIL line per environment
# (validate.sh starts its own container on :6390 and copies the working tree; it is listed last and runs alone.)
set -uo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6"
WORK="$(mktemp -d)"
LOGS="$WORK/logs"; mkdir -p "$LOGS"
git -C "$SRC" diff --quiet HEAD || echo "note: uncommitted edits are NOT tested here (this runs the committed HEAD $(git -C "$SRC" rev-parse --short HEAD))"

# name | python | port | command
ENVS=(
  "01 pytest py3.12|3.12|6511|uv run pytest -q"
  "02 pytest py3.13|3.13|6512|uv run pytest -q"
  "03 pytest py3.14|3.14|6513|uv run pytest -q"
  "04 ten worlds py3.12|3.12|6514|uv run python scripts/ten_worlds.py"
  "05 ten worlds py3.13|3.13|6515|uv run python scripts/ten_worlds.py"
  "06 ten worlds py3.14|3.14|6516|uv run python scripts/ten_worlds.py"
  "07 counterfactual py3.12|3.12|6517|uv run python scripts/counterfactual_eval.py --worlds 30"
  "08 held-out py3.13|3.13|6518|uv run python scripts/heldout_eval.py --worlds 40 --pipeline-worlds 10"
  "09 demo path py3.14|3.14|6519|uv run quarantine session1 --graph e9 && uv run quarantine flag doc_7 --graph e9 && uv run quarantine session2 --kill-planner --graph e9 && uv run quarantine status --graph e9"
  "10 mutation py3.13|3.13|6520|uv run python scripts/mutation_check.py"
)
run_one() {
  local name="${1%%|*}"; local rest="${1#*|}"; local py="${rest%%|*}"; rest="${rest#*|}"; local port="${rest%%|*}"; local cmd="${rest#*|}"
  local id="${name%% *}"; local dir="$WORK/$id"; local cname="qmatrix-$id-$$"
  git clone -q "$SRC" "$dir" && git -C "$dir" checkout -q "$(git -C "$SRC" rev-parse HEAD)"
  docker run -d --name "$cname" -p "127.0.0.1:$port:6379" "$IMAGE" >/dev/null
  for i in $(seq 1 40); do docker exec "$cname" redis-cli ping 2>/dev/null | grep -q PONG && break; sleep 1; done
  ( cd "$dir" && export UV_PYTHON="$py" FALKORDB_PORT="$port" && uv sync --all-extras -q && eval "$cmd" ) > "$LOGS/$id.log" 2>&1
  local rc=$?
  docker rm -f "$cname" >/dev/null 2>&1
  [ $rc -eq 0 ] && echo "PASS  $name" || echo "FAIL  $name   (log: $LOGS/$id.log)"
}
export -f run_one; export WORK LOGS SRC IMAGE
printf '%s\n' "${ENVS[@]}" | xargs -P 5 -I{} bash -c 'run_one "$@"' _ {}
echo "logs: $LOGS"
