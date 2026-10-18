# Review brief for Aashna: merge gate for branch `improve`

**Status Sun 2026-10-18:** this review did not happen. Aashna had not sent results by Sunday morning, and Parth pushed `improve` to `main` himself (GitHub `main` = `improve` = tag `freeze-sat` = b31ba1e). No `submit-candidate` tag exists. The steps below are still the right checks for anyone reviewing the code. Section 1 was run on Oct 18 in a fresh GitHub clone by Parth with Claude (221 tests, ten worlds, compose check, demo path, junk MCP input); see `docs/CHECKLIST-AASHNA.md`.

---

You are the merge gate. Parth builds on `improve`; nothing lands on `main` until you sign off. The Thursday baseline is the tag `freeze-v1`. If `improve` is not ready by Sat 18:00 EDT, we submit `freeze-v1`.

When this brief was written (Fri 2026-10-16) the change was 14 commits, 30 files, +1858 / -172 lines. At b31ba1e, `git diff --shortstat freeze-v1..improve` gives 58 files, +5387 / -754. At b31ba1e, `quarantine/` holds 2,243 lines and `tests/` 3,069 lines (`wc -l`).

## 0. Get the code

Repo: https://github.com/Ps23102004/graphhacks-quarantine (branches `main` and `improve`, tags `freeze-v1` and `freeze-sat`). It is private until Parth makes it public. To get in, ask Parth to add your GitHub username as a collaborator (Settings, Collaborators) and accept the emailed invite. Then:

```bash
git clone https://github.com/Ps23102004/graphhacks-quarantine.git && cd graphhacks-quarantine
git checkout improve
```

Tools needed: Docker, `uv`.

## 1. Run these first (about 30 minutes, on your machine, not Parth's)

```bash
docker run -d --name quarantine-falkordb -p 127.0.0.1:6379:6379 -p 127.0.0.1:3000:3000 \
  falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
uv sync --all-extras                  # --all-extras matters: the MCP tests need the optional SDK
uv run pytest -q                      # expect: all passed, 0 failed (221 tests at b31ba1e; see docs/TESTING.md). Note any skips.
scripts/validate.sh                   # expect: "validation: N passed, 0 failed" (copies the working tree, uncommitted edits included; starts its own FalkorDB on :6390)
scripts/validate_compose.sh           # expect: "Compose validation complete: ALL PASS" (fixed and re-run on Oct 18, commit b31ba1e)
uv run python scripts/heldout_eval.py --worlds 100 --pipeline-worlds 30   # expect: 0 graph != oracle, 0 invariant violations
uv run python scripts/counterfactual_eval.py --worlds 20   # expect: 0 invented receipts, 0 wrong 'clean' answers, 0 page != graph; misses only in the UNRECORDED influence row (see docs/COUNTERFACTUAL.md)
uv run python scripts/mutation_check.py   # about 20 min; expect: 0 unexpected survivors (3 documented equivalent mutants are excluded)
```

Then the demo by hand, in two terminals. This is the exact video path:

```bash
uv run python web/server.py                          # page at http://localhost:8765
uv run quarantine session1 --slow 0.4
uv run quarantine flag doc_7                         # expect: quarantined 6 | wipe agents 25 | roll back 19, and an "in words:" line
uv run quarantine session2 --kill-planner            # expect: "kill -9, exit -9", then lease takeover, rounds [1, 2, 2, 0]
uv run quarantine session1 --fixture fixtures/support-crew.yaml --graph sc
uv run quarantine flag kb_5 --fixture fixtures/support-crew.yaml --graph sc   # expect: quarantined 7 | wipe agents 21 | roll back 17
uv run python scripts/mcp_inspect.py call why_connected '{"from_id": "a_requirements", "to_id": "doc_7"}'   # expect: shape "path", 4 hops
```

Write down anything that differs from "expect". A fresh-machine failure is worth more than any code finding.

## 2. What to read, in priority order

| # | where | why it matters | what to look for |
|---|---|---|---|
| 1 | `quarantine/loader.py` `rework`, `derive_rework`, `write_procedure` | the write path | fencing (author, session, lease), atomicity of the single-statement write, the empty-read-set branch, `needs_regeneration` / `ungrounded` / `REWORKED_FOR`, anything that lets a clean memory cite a quarantined one |
| 2 | `quarantine/queries.py` (diff vs `freeze-v1`) | every Cypher statement | `TAINT_CLOSURE` is unbounded (`*1..`): confirm it terminates if a cycle is ever written. `SUPPORT_AND_HEALABLE` and `HEAL_FACTS` both encode the heal rule (strict plurality, at least 2): two copies that must agree, so check for drift. `HEAL_FACTS` uses `FOREACH` to record the outvoted clean episodes as `OUTVOTED` edges, which the closure and receipts do not follow. `CREATE_REWORK_TASKS` adds `FOLLOWS` |
| 3 | `quarantine/answers.py` (224 lines at b31ba1e) | the fixed tool catalog the organizers' guide asks for | `valid_id` and the resolvers run before any query; `sentence()` raises on malformed paths; `why_connected` uses `algo.SPpaths` and falls back to `shortestPath` only if it raises; `blast_radius` runs one receipt query per member (fine at 25 nodes, slow at thousands) |
| 4 | `quarantine/mcp_server.py` | what a real AI host would call | every tool should answer in one of four shapes (`path`, `memory`, `not_in_graph`, `unknown`). `_recovery()` used to loop over module names with `except Exception: continue`, which hid real failures; it now calls `recovery_status` directly and reports the real error (`tests/test_mcp.py`) |
| 5 | `web/server.py`, `web/index.html` | the video's main screen | reads only through `ro_query`; the Host-header check; all agent text escaped (XSS fix from the Thursday review); the hatched ochre "naive wipe" views; behaviour with two flagged docs (counters go blank on purpose) |
| 6 | `quarantine/worldgen.py`, `heldout.py` | the "unseen data" evidence | the oracle must really be independent of the Cypher (it is plain Python sets); would a bug in both go unnoticed? |
| 7 | `docs/GUIDELINE-CONFORMANCE.md`, `docs/EVAL-HELDOUT.md` | claims the README makes | every claim has a test and an honest limit; flag any sentence that overstates |
| 8 | `deploy/docker-compose.yml`, `scripts/validate_compose.sh` | "local to live by env vars" | `docker compose config` with `FALKORDB_HOST` etc. set shows them in the web service; nobody has tried a real FalkorDB Cloud instance |

## 3. Try to break it (pick at least four)

1. Flag a document, then run `session2` twice in a row. The second run should change nothing (`rounds [0]`), not write duplicates.
2. Flag two documents (`doc_7` then `doc_4`) and run `session2`. Is anything left deadlocked? Does the page show sensible receipts?
3. Stop `session2` with Ctrl-C halfway (not the planned kill), then rerun it. Does it recover? The code claims restart recovery.
4. Call every MCP tool with hostile input: `None`, `123`, `"\u0000"`, a 100,000-character string, `"' }) MATCH (n) DETACH DELETE n //"`. Expected: shape `unknown`, nothing deleted.
5. Point `--graph` at a name that does not exist. Expected at b31ba1e: `flag`, `unflag`, `session2` and `status` refuse with "does not exist" and create no graph (checked Oct 18). Only `session1` creates one. Look for any other path that does.
6. Run with `FALKORDB_PORT` pointing at a second container while the demo one is running. Nothing should touch the wrong one.
7. Write one new held-out generator setting we did not think of (many agents, very wide facts, a fact supported only by poisoned episodes) and see if graph and oracle still agree.
8. Flag `doc_7`, then `uv run quarantine unflag doc_7` (retract a false alarm): nothing should stay red. After `session2` has started healing, `unflag` must refuse.
9. Read `tests/test_guideline.py` and `tests/test_track02_bar.py` as a skeptic: is any assertion true by construction? (Twelve AI skeptics did this once; see `docs/GUIDELINE-CONFORMANCE.md`. A human pass is different.)

## 4. Known weak spots (do not rediscover these, but do judge whether they matter)

- The agents are scripted. Graph writes, read-set capture, closure, heal, claims and leases are real; the agent "decisions" are fixture text or graph-derived placeholders. The video and README must say so.
- Read sets are the per-write lists in the fixture. If each step and artifact also counted everything its author read or wrote earlier, the demo closure would be 9 memories, not 6 (`worldgen._make_cumulative` on the fixture; see `docs/TESTING.md`). The held-out "cumulative" row measures this in random worlds.
- The heal threshold (2) and the strict-plurality rule are constants in Cypher. Only the lease length is read from the `Procedure` node.
- Tenant isolation is by graph name on one FalkorDB instance, not by credential.
- The kickoff email's guide was paraphrased by the team and not re-read (`docs/GUIDELINE-CONFORMANCE.md`). Aman was asked to check it; no check is recorded. The six rules may be slightly off.
- FalkorDB Cloud has never been tried. Only the connection arguments and `docker compose config` are tested.
- `scripts/check_browser.js` checks the page at 1920, 960 and 375 px wide, not on a projector. Quarantined, healed and naive-casualty chips carry markers (`!`, `+`, `×`) besides colour, but nobody colour-blind has looked.

## 5. Merge criteria (all must be true)

- [ ] `uv run pytest -q` passes on your machine with no unexpected skips (state the count).
- [ ] `scripts/validate.sh` 0 failed; `scripts/validate_compose.sh` all checks pass.
- [ ] `scripts/mutation_check.py`: 0 unexpected survivors.
- [ ] The hand-run demo above gives the expected numbers (6 / 25 / 19 and 7 / 21 / 17) and the kill beat works.
- [ ] No blocker is open. Blocker = a wrong number on the demo path, a clean memory that can cite a quarantined one, a crash on the demo path, a secret or credential in git history (`git log -p | grep -iE 'password|secret|token'`), or a claim in the docs that the code does not support.
- [ ] You have read items 1 to 4 in section 2 end to end and can explain `rework` and `HEAL_FACTS` out loud.
- [ ] You tried at least four items from section 3 and wrote down what happened.
- [ ] `docs/VALIDATION.md` and `docs/GUIDELINE-CONFORMANCE.md` match what you saw (fix any stale number).

Then merge `improve` into `main` yourself (fast-forward if possible), tag it `submit-candidate`, and tell Parth. Parth does not merge his own branch.

## 6. How to report

Step-by-step checklists: `docs/CHECKLIST-AASHNA.md` (yours) and `docs/CHECKLIST-AMAN.md`. Put findings in the filled checklist you send Parth, one per line: `severity (blocker / should-fix / nit) | file:line | what you did | what happened | smallest fix`. Where you can, add a failing test under `tests/` instead of prose; a red test is the clearest bug report. Send blockers right away, the rest at the Sat 10:00 EDT checkpoint.

## 7. Schedule (as planned on Friday)

- Fri: sections 0 and 1; message Parth with the results.
- Sat by 10:00: sections 2 and 3 done; findings filed.
- Sat by 14:00: Parth has fixed blockers; you re-run section 1 on the fixed commit.
- Sat by 18:00: merge decision. If any blocker is open, we submit `freeze-v1`.
