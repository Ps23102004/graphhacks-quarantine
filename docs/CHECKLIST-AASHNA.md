# Aashna: fresh clone, test and review checklist (Sat night / Sun morning IST)

## Status Sun 2026-10-18

Aashna ran two tests and sent reports. On Oct 16 she ran the demo from a zip on Windows. On Oct 18 she tested branch `improve` at e92cd46 on Windows: 131 tests passed (the suite has grown since: later commits added regression tests), the demo matched the README, and she found seven defects (D1 to D7). Each was fixed in later commits (see `tests/test_attack_regressions.py` and `git log`). Her `kill -9` finding is why the README notes that the killed process exits with 1 on Windows.

Parth, working with Claude, also ran a fresh clone from GitHub on macOS: 221 tests passed, and `scripts/ten_worlds.py`, `scripts/validate_compose.sh`, the demo path in section 1 and the junk-input MCP call in section 3 passed. The section 4 code review and the merge decision in section 5 were not done by a second person.

`docs/RUNS.md` lists what was run on the final commit.

The plan as written on Saturday follows.

---

Goal: prove a stranger can run QUARANTINE from a clean clone, and that nothing on screen is false. Write down every step that differs from "expect". Send the filled checklist to Parth by **Sunday 08:00 EDT (17:30 IST)**. If something fails, stop and send it right away. Do not fix code yourself unless Parth asks.

Tag `freeze-sat` was added on Sunday morning, after this checklist was written; check out `improve` or the tag. Tools: Docker Desktop running, `uv`, `git`, Chrome.

## Windows notes (from your first report)
- Clone the tag fresh. Do not reuse the Oct 16 zip. Fixed since then: the test port default (now 6379), the Windows venv path in `tests/test_packaging.py`, MCP tests no longer depend on the working directory, the README shows the real healing query and no longer mentions Graphiti or Vector TTL, and a missing graph shows an empty page (no traceback).
- `--kill-planner` exits with 1, not -9, on Windows. That is expected. The lease takeover is what to check. The video is recorded on the Mac.
- Still open (not blocking): a live deployment needs the public hostname added to `ALLOWED_HOSTS` (see `deploy/docker-compose.yml`). We are not deploying.

## 0. Get the code (5 min)
- [ ] Accept the GitHub collaborator invite (the repo is private until Parth makes it public).
- [ ] `git clone https://github.com/Ps23102004/graphhacks-quarantine.git && cd graphhacks-quarantine && git checkout freeze-sat`

## 1. Follow the README cold (20 min)
Use ONLY the README's "Run it locally" steps, word for word, in a new terminal. Do not use anything you remember from before.
- [ ] The FalkorDB `docker run` works. If port 6379 is taken, note it.
- [ ] `uv sync --all-extras` works.
- [ ] `uv run pytest -q` -> expect all passed, `0 failed` (221 tests at b31ba1e; see `docs/TESTING.md`). Note the time and any skips.
- [ ] Demo, two terminals: `uv run python web/server.py`, open http://localhost:8765; then `uv run quarantine session1 --slow 0.4`, `uv run quarantine flag doc_7`, `uv run quarantine session2 --kill-planner`.
  - [ ] flag prints `quarantined 6 | wipe agents 25 | roll back 19`
  - [ ] page: 6 red chips, headline "6 of 25 memories", the Quarantined list shows ep_7a, ep_7b, f_http_client, f_http_pin, step_3, a_requirements
  - [ ] click `a_requirements`: a yellow highlighter path to doc_7 and a sentence under "Why is it red?"
  - [ ] session2: "kill -9", lease takeover, rounds [1, 2, 2, 0]; the page shows green replacement chips under f_http_client, step_3 and a_requirements
- [ ] Every command the README shows ran without editing it. List any that needed a change.

## 2. Validation scripts (40 min, can run while you read)
- [ ] `scripts/validate.sh` -> expect `0 failed` (on Windows the kill-planner check expects exit 1, not -9). It starts its own FalkorDB on :6390.
- [ ] `scripts/validate_compose.sh` -> expect `Compose validation complete: ALL PASS`
- [ ] `uv run python scripts/heldout_eval.py --worlds 50 --pipeline-worlds 10` -> expect `0` in the "graph != oracle" and "invariant violations" columns
- [ ] `uv run python scripts/counterfactual_eval.py --worlds 20` -> exit code 0. Expect `0` false negatives on the first three rows. The UNRECORDED-influence row is nonzero by design (9% at 20 worlds, 7% at 150): it is the measured miss when influence is not recorded as a read. Expect `0` invented receipts, wrong 'clean' answers and page != graph on every row.
- [ ] `uv run python scripts/ten_worlds.py` -> every line `ok` (under a minute)
- [ ] Optional if time: `uv run python scripts/mutation_check.py` (about 20 min) -> 0 unexpected survivors

## 3. Try to break it (pick at least five, 30 min)
Use a separate graph so the demo graph stays clean. Add `--graph test` to every `quarantine` command, start the page with `uv run python web/server.py --graph test`, and set `QUARANTINE_GRAPH=test` in the shell before the MCP commands (the MCP tools read that variable; the default is `quarantine`).
- [ ] Flag a document that does not exist: `uv run quarantine flag doc_999 --graph test` -> an error naming doc_999, nothing red
- [ ] Flag doc_7, then `uv run quarantine unflag doc_7 --graph test` -> "quarantined now: 0", page clean
- [ ] Flag doc_7, run session2, then unflag -> it must refuse with "healing has already started"
- [ ] Run `session2` twice -> the second run prints `rounds [0]` and changes nothing
- [ ] Flag two documents (`doc_7` and `doc_3`) -> the page banner names both and the three counters go blank
- [ ] Second world: `uv run quarantine session1 --fixture fixtures/support-crew.yaml --graph sc` then `uv run quarantine flag kb_5 --fixture fixtures/support-crew.yaml --graph sc` -> `quarantined 7 | wipe agents 21 | roll back 17`
- [ ] MCP tool with junk input: `uv run python scripts/mcp_inspect.py list` shows the six tools (`inspect_quarantined_memories`, `trace_provenance_receipt`, `why_connected`, `recall`, `blast_radius`, `get_recovery_status`). Then `uv run python scripts/mcp_inspect.py call trace_provenance_receipt '{"memory_id": "x\"}) DETACH DELETE (n) //"}'` -> shape `unknown`, and `uv run quarantine status --graph test` prints the same JSON before and after
- [ ] Page at phone width (Chrome devtools, 375 px): no horizontal page scroll; the chart scrolls inside its frame

## 4. Review (60 min, read the diff, not the whole repo)
`git diff freeze-v1..freeze-sat --stat`, then read in this order:
- [ ] `quarantine/loader.py` `unflag` and `reconcile`, and in `quarantine/queries.py` `UNFLAG_DOC`, `HEAL_STARTED` and `CLEAR_STALE`: can they leave a memory clean that a still-flagged document reaches?
- [ ] `quarantine/counterfactual.py`: is "truly affected" computed independently of the Cypher? Could it hide a false negative?
- [ ] Each fix commit since `freeze-v1`: does it have a test that fails without it?
- [ ] README: every number matches what you saw in sections 1 to 3. Mark any sentence you could not verify.

## 5. Send back
- [ ] For each section: PASS, or the exact command plus the output that differed.
- [ ] Your merge decision: `improve` -> `main` yes or no, and why.
