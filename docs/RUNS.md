# Run record

What was run, on which commit, and what it printed. Code commit for all rows: `3874be2` (Oct 18, 10:07 EDT). Commits after it change documentation, the launch assets, and the wording that two checks in `scripts/check_browser.js` look for. Check with `git diff 3874be2..HEAD --stat -- . ':!*.md' ':!docs/media'`, which lists `scripts/check_browser.js` (two banner strings) plus a comment in `quarantine/queries.py` and a docstring in `tests/test_track02_bar.py`. None changes behaviour.

Parth ran everything below with Claude, on macOS, against FalkorDB 6.0.2 (`falkordb/falkordb:6.0.2@sha256:107455e8...`). Aashna ran branch `improve` at e92cd46 on Windows on Oct 18 and reported seven defects, all fixed since (see `docs/CHECKLIST-AASHNA.md`). Nobody else has run the final commit.

## Ten environments (`scripts/env_matrix.sh`)

Fresh clones of the commit, each with its own throwaway FalkorDB. Output:

```
PASS  01 pytest py3.12         221 passed in 97.70s
PASS  02 pytest py3.13         221 passed in 97.84s
PASS  03 pytest py3.14         221 passed in 101.89s
PASS  04 ten worlds py3.12
PASS  05 ten worlds py3.13
PASS  06 ten worlds py3.14
PASS  07 counterfactual py3.12 (--worlds 30)
PASS  08 held-out py3.13       (--worlds 40 --pipeline-worlds 10)
PASS  09 demo path py3.14      quarantined 6 | wipe agents 25 | roll back 19; kill -9, exit -9; fixpoint: rounds [1, 2, 2, 0], 28 memories
PASS  10 mutation py3.13       0 unexpected survivor(s) of 32 mutations (30 caught, 2 survived: the documented equivalent mutants)
```

## Other checks on the same code

| check | result |
|---|---|
| `scripts/validate.sh` | `validation: 29 passed, 0 failed` (pytest inside it: 221 passed) |
| `scripts/validate_compose.sh` | `Compose validation complete: ALL PASS` |
| `scripts/ten_worlds.py` | `ok` on all ten worlds (demo, support crew, six generated crews, wide fan-out, dissent-heavy) |
| `scripts/check_browser.js` | 40 of 40 checks passed (rerun after the banner wording in two of the checks was updated, on commit `013cdfd`, which is the first commit with the updated check script) |
| `scripts/heldout_eval.py --worlds 40 --pipeline-worlds 10` | 0 graph-vs-oracle mismatches in 357 cases per model; 0 invariant violations in 98 runs per model |

## 150-world counterfactual evaluation (`uv run python scripts/counterfactual_eval.py --worlds 150`)

Run on commit `c4de91d`, which has the same engine code as `3874be2` (and as the final commit). The numbers are identical to the first run of Oct 17, because the seeds are fixed.

```
| world model | (world, doc) runs | truly affected | quarantined | false negatives | needless flags | needless facts that cannot heal | invented receipts | wrong 'clean' answers | page != graph |
|---|---|---|---|---|---|---|---|---|---|
| declared read sets | 1340 | 3895 | 10496 | 0 runs, 0 memories (0% of truly affected) | 6601 (63% of flagged) | 457 | 0 | 0 | 0 |
| cumulative context | 1340 | 4458 | 11850 | 0 runs, 0 memories (0% of truly affected) | 7392 (62% of flagged) | 457 | 0 | 0 | 0 |
| deep chains | 1340 | 7646 | 22051 | 0 runs, 0 memories (0% of truly affected) | 14405 (65% of flagged) | 457 | 0 | 0 | 0 |
| UNRECORDED influence (graph: declared reads; truth: whole context) | 1340 | 4458 | 10496 | 169 runs, 329 memories (7% of truly affected) | 6367 (61% of flagged) | 457 | 0 | 0 | 0 |
```

## After publishing

An anonymous clone of the public repository (`git clone https://github.com/Ps23102004/graphhacks-quarantine.git`, commit `531d7eb`, no credentials): `uv run pytest -q` gave 221 passed, and the demo path printed `quarantined 6 | wipe agents 25 | roll back 19`, `kill -9, exit -9` and `fixpoint: rounds [1, 2, 2, 0], 28 memories`.

## What was not run

- A dedicated security scanner (the AI attackers in `docs/ATTACK-LOG.md` included one on web security).
- Any run by a second person on the final commit.
- A live deployment (there is none).
