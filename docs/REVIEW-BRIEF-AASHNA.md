# Review brief for Aashna: merge gate for branch `improve`

You are the merge gate. Parth builds on `improve`; nothing lands on `main` until you sign off. The Thursday baseline is the tag `freeze-v1` (also what `main` is at), so if `improve` is not ready by Sat 18:00 EDT we submit `freeze-v1` and lose nothing.

Size of the change when this brief was written (Fri 2026-10-16; it has grown since): 14 commits, 30 files, +1858 / -172 lines. Run `git diff --shortstat freeze-v1..improve` for the current size. About 1,600 lines of product code in `quarantine/`, about 1,100 lines of new tests.

## 0. Get the code

Private repo: https://github.com/Ps23102004/graphhacks-quarantine (branches `main` and `improve`, tag `freeze-v1`). A private GitHub repo opens only for people who were added: ask Parth to add your GitHub username as a collaborator (Settings, Collaborators), accept the emailed invite, then:

```bash
git clone https://github.com/Ps23102004/graphhacks-quarantine.git && cd graphhacks-quarantine
git checkout improve
```

Tools needed: Docker, `uv`.

## 1. Run these first (about 30 minutes, all on your machine, not Parth's)

```bash
docker run -d --name quarantine-falkordb -p 6379:6379 -p 3000:3000 \
  falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
uv sync --all-extras                  # --all-extras matters: the MCP tests need the optional SDK
uv run pytest -q                      # expect: all passed, 0 failed (about 1 to 2 min; the count changes, see docs/TESTING.md). Note any skips.
scripts/validate.sh                   # expect: validation: N passed, 0 failed (about 3 min; copies the working tree, uncommitted edits included; starts its own FalkorDB on :6390)
scripts/validate_compose.sh           # expect: all checks pass. NOT re-run since Friday's compose change: this is the one to watch
uv run python scripts/heldout_eval.py --worlds 100 --pipeline-worlds 30   # expect: 0 graph != oracle, 0 violations
uv run python scripts/counterfactual_eval.py --worlds 20   # expect: 0 false negatives, 0 invented receipts (see docs/COUNTERFACTUAL.md)
uv run python scripts/mutation_check.py   # about 20 min; expect: 0 unexpected survivors (2 documented equivalent mutants are fine)
```

Then the demo by hand, in two terminals (this is the exact video path):

```bash
uv run python web/server.py                          # page at http://localhost:8765 (port 8000 may be taken on some machines)
uv run quarantine session1 --slow 0.4
uv run quarantine flag doc_7                         # expect: precise 6 | per-agent 25 | time-based 19, and an "in words:" line
uv run quarantine session2 --kill-planner            # expect: "kill -9, exit -9", then lease takeover, rounds [1, 2, 2, 0]
uv run quarantine session1 --fixture fixtures/support-crew.yaml --graph sc
uv run quarantine flag kb_5 --fixture fixtures/support-crew.yaml --graph sc   # expect: precise 7 | per-agent 21 | time-based 17
uv run python scripts/mcp_inspect.py call why_connected '{"from_id": "a_requirements", "to_id": "doc_7"}'
```

Write down anything that differs from "expect". A fresh-machine failure is worth more than any code finding.

## 2. What to read, in priority order

| # | where | why it matters | what to look for |
|---|---|---|---|
| 1 | `quarantine/loader.py` `rework`, `derive_rework`, `write_procedure` | the write path; an earlier version copied poisoned text into a clean twin | fencing (author, session, lease), atomicity of the single-statement write, the empty-read-set branch, `needs_regeneration` / `ungrounded` / `REWORKED_FOR`, anything that lets a clean memory cite a quarantined one |
| 2 | `quarantine/queries.py` (diff vs `freeze-v1`) | every Cypher statement | `TAINT_CLOSURE` is now unbounded (`*1..`): confirm it terminates on cycles if anyone ever writes one. `SUPPORT_AND_HEALABLE` and `HEAL_FACTS` both encode the heal rule (strict plurality, at least 2): two copies that must agree, so check for drift. `HEAL_FACTS` uses `FOREACH` to record the outvoted clean episodes as `OUTVOTED` edges, which the closure and receipts do not follow. `CREATE_REWORK_TASKS` adds `FOLLOWS` |
| 3 | `quarantine/answers.py` (new, 189 lines) | the fixed tool catalog the organizers' guide asks for | `valid_id` and the resolvers run before any query; `sentence()` raises on malformed paths; `why_connected` uses `algo.SPpaths` and falls back to `shortestPath` only if it raises; `blast_radius` runs one receipt query per member (fine at 25 nodes, slow at thousands) |
| 4 | `quarantine/mcp_server.py` | what a real AI host would call | every tool should answer in one of four shapes (`path`, `memory`, `not_in_graph`, `unknown`). **Smell:** `_recovery()` loops over module names with `except Exception: continue`, which can hide a real failure. Decide whether to tighten it |
| 5 | `web/server.py`, `web/index.html` | the video's main screen | reads only via `ro_query`; host-header check; all agent text escaped (XSS fix from the Thursday review); the hatched ochre "naive wipe" casualty views; behaviour with two flagged docs (counters intentionally go blank) |
| 6 | `quarantine/worldgen.py`, `heldout.py` | the "unseen data" evidence | the oracle must really be independent of the Cypher (it is plain-Python sets); would a bug in both go unnoticed? |
| 7 | `docs/GUIDELINE-CONFORMANCE.md`, `docs/EVAL-HELDOUT.md` | claims we will make in the README | every claim has a test and an honest limit; flag any sentence that overstates |
| 8 | `deploy/docker-compose.yml`, `scripts/validate_compose.sh` | "local to live by env vars" | `docker compose config` with `FALKORDB_HOST` etc. set shows them in the web service; nobody has tried a real FalkorDB Cloud instance |

## 3. Try to break it (pick at least four)

1. Flag a document, then run `session2` twice in a row. Second run should be a no-op fixpoint, not duplicates.
2. Flag two documents (`doc_7` then `doc_4`), run `session2`. Anything left deadlocked? Does the page show sensible receipts?
3. Kill `session2` with Ctrl-C halfway (not the planned kill), then rerun it. Does it recover (the code claims restart recovery)?
4. Call every MCP tool with hostile input: `None`, `123`, `"\u0000"`, a 100,000-character string, `"' }) MATCH (n) DETACH DELETE n //"`. Expected: shape `unknown`, nothing deleted.
5. Point `--graph` at a name that does not exist. Known gap: some write-path commands create an empty graph; list which ones.
6. Run with `FALKORDB_PORT` pointing at a second container while the demo one is running; nothing should touch the wrong one.
7. Write one new held-out generator setting we did not think of (many agents, very wide facts, a fact supported only by poisoned episodes) and see if graph and oracle still agree.
8. Flag `doc_7`, then `uv run quarantine unflag doc_7` (retract a false alarm): nothing should stay red. After `session2` has started healing, `unflag` must refuse.
9. Read `tests/test_guideline.py` and `tests/test_track02_bar.py` as a skeptic: is any assertion true by construction? (Twelve AI skeptics already did this once; a human pass is different.)

## 4. Known weak spots (do not rediscover these, but do judge whether they matter)

- The agents are scripted. Graph writes, read-set capture, closure, heal, claims and leases are real; the agent "decisions" are fixture text or graph-derived placeholders. The video and README must say so.
- Read sets are the per-write lists in the fixture. An independent review earlier reported that counting an agent's whole accumulated context would give a larger closure (9, not 6); the held-out "cumulative" row measures that in random worlds, not on the demo.
- The heal threshold (2) and the strict-plurality rule are constants in Cypher; only the lease length is read from the `Procedure` node.
- Tenant isolation is by graph name on one FalkorDB instance, not by credential.
- The kickoff email's guide was paraphrased by Parth, not read by us; Aman is confirming it. The six rules may be slightly off.
- FalkorDB Cloud has never been tried; only the connection arguments and `docker compose config` are tested.
- The page is checked by `scripts/check_browser.js` at 1920, 960 and 375 wide, not on a projector; quarantined, healed and naive-casualty chips carry label markers (`!`, `+`, `×`) besides colour, but nobody colour-blind has looked.

## 5. Merge criteria (all must be true)

- [ ] `uv run pytest -q` passes on your machine with no unexpected skips (state the count).
- [ ] `scripts/validate.sh` 0 failed; `scripts/validate_compose.sh` all checks pass.
- [ ] `scripts/mutation_check.py`: 0 unexpected survivors.
- [ ] The hand-run demo above produces the expected numbers (6 / 25 / 19 and 7 / 21 / 17) and the kill beat works.
- [ ] No finding rated blocker is open. Blocker = wrong number on the demo path, a clean memory that can cite a quarantined one, a crash on the demo path, a secret or credential in git history (`git log -p | grep -iE 'password|secret|token'`), or a claim in the docs that the code does not support.
- [ ] You have read items 1 to 4 in section 2 end to end and can explain `rework` and `HEAL_FACTS` out loud.
- [ ] You tried at least four items from section 3 and wrote down what happened.
- [ ] `docs/VALIDATION.md` and `docs/GUIDELINE-CONFORMANCE.md` match what you saw (fix any number that is stale).

Then merge `improve` into `main` yourself (fast-forward if possible), tag it `submit-candidate`, and tell Parth. Parth does not merge his own branch.

## 6. How to report

Step-by-step checklists exist: `docs/CHECKLIST-AASHNA.md` (yours) and `docs/CHECKLIST-AMAN.md`. Put findings in the filled checklist you send Parth, one per line: `severity (blocker / should-fix / nit) | file:line | what you did | what happened | smallest fix`. Where you can, add a failing test under `tests/` instead of prose; a red test is the clearest bug report. Send Parth the blockers immediately, the rest at the Sat 10:00 EDT checkpoint (fresh-clone gate).

## 7. Schedule

- Today (Fri): sections 0 and 1; message Parth with the results.
- Sat by 10:00: sections 2 and 3 done; findings filed.
- Sat by 14:00: Parth has fixed blockers; you re-run section 1 on the fixed commit.
- Sat by 18:00: merge decision. If any blocker is open, we submit `freeze-v1`.
