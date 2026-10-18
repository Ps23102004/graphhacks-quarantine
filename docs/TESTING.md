# TESTING — how to know Quarantine works

Several layers, from fastest to most convincing. Anyone on the team (or a judge) can run all of them.

## 0. Prerequisites

- Docker running, `uv` installed (https://docs.astral.sh/uv/), Python 3.12+.
- FalkorDB 6.0.2 pinned by digest. FalkorDB is source-available (SSPL), not open source.

```bash
docker run -d --name quarantine-falkordb -p 127.0.0.1:6379:6379 -p 127.0.0.1:3000:3000 \
  falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
uv sync --all-extras                      # --all-extras installs the optional MCP SDK the MCP tests need
```

## 1. Unit and integration tests (about 1 to 2 min)

```bash
uv run pytest -q          # expect: all tests pass, 0 failed
```

The number of tests changes as tests are added, so no doc states it: read the count from pytest's summary line.

Tests use their own graphs (none is named `quarantine`) and delete them afterwards. They never touch the demo graph named `quarantine`.

## 2. Working-tree validation (a few minutes): close to what a stranger would see

```bash
scripts/validate.sh       # expect: "validation: N passed, 0 failed" (N changes as checks are added)
```

Copies the working tree, uncommitted edits included (`.git` and `.venv` excluded), into a temp dir, starts a throwaway FalkorDB on :6390, installs from the lockfile, runs pytest, then runs the real CLI and checks the exact lines the video says (6 vs 25 vs 19, the receipt, the heal, the kill-Planner takeover, the control closure for doc_5, the page JSON and its Host check). Because it copies the working tree, it is not a fresh clone: run it on a clean tree (`git status` empty) to validate a commit, and note that it cannot catch a needed file that was never committed.

## 3. Mutation check (slow: one pytest run per mutation): do the tests actually catch breakage?

```bash
uv run python scripts/mutation_check.py     # expect: "0 unexpected survivor(s)"
```

Breaks one thing at a time in a throwaway clone of the committed HEAD (the `MUTATIONS` list in `scripts/mutation_check.py`: closure edge types and depth, heal threshold and tie rule, episodes healable, blockers, lease expiry and holder, claim ownership, COMPLETE session and replacement checks, rework guard and idempotence, baselines, a fixture read set, page counters, twin detection, receipts). pytest must go red each time. Two documented equivalent mutants survive and are excluded from the count (the heal query's `>= 2` check and its tie check, both already guarded by the `healable` flag).

## 4. Browser regressions (optional, installed Playwright CLI)

Start the page against a graph already seeded with `quarantine session1`. With Playwright CLI and Chrome already installed:

```bash
playwright-cli -s=quarantine-ui-check open http://localhost:8765 --browser chrome
playwright-cli -s=quarantine-ui-check run-code --filename scripts/check_browser.js
playwright-cli -s=quarantine-ui-check close
```

Expect every check to report `passed: true`. This runs the real ledger page (no chart library), substitutes only `/graph` and `/receipt` responses, and never writes to FalkorDB. It covers every cell staying visible at 1920, 960 and 375 px, no horizontal scroll on a phone, the quarantine counter climbing with the red wave, non-colour markers (`!`, `+`, `×`), the receipt highlighting four ribbons and reading as a sentence, the two naive-wipe views painting 13 and 19 clean casualties, healed twins fitting, keyboard selection, reset cleanup, and a receipt arriving after reset. It supplements the live CLI run; it does not prove graph queries or process recovery. The Python suite does not require Playwright.

## What each claim is tested by

| claim (what the video says) | test | independent of the fixture's tuning? |
|---|---|---|
| Fixture is well formed; read sets only point backwards in time | `test_fixture_loads_and_is_consistent` | yes (audit queries) |
| Flagging doc_7 quarantines 6; per-agent wipe would hit 25; time-based 19 | `test_closure_is_precise_and_baselines_are_not` | numbers come from the fixture's `expected:` block |
| The receipt is a 4-hop shortestPath through the Planner | `test_receipt_is_a_shortest_path_through_the_planner` | yes (path asserted hop by hop) |
| Clean support counts and rework blockers | `test_support_counts_and_rework_ordering` | partly |
| Session 2 heals the package fact, then reworks in dependency order, rounds [1, 2, 2, 0] | `test_session2_heals_then_reworks_in_dependency_order` | partly |
| Each agent's start-up query sees only its own quarantined work | `test_startup_query_is_per_agent` | yes |
| Kill the Planner mid-rework: Coder stays blocked, live lease refuses a second claim, expired lease is taken over | `test_kill_planner_mid_rework_coder_stays_blocked` | yes |
| A rework write refuses to cite unreplaced quarantined memory | `test_rework_refuses_to_cite_unreplaced_quarantined_memory` | yes |
| The three CLI commands print the same numbers end to end | `test_cli_runs_the_three_commands_end_to_end` | via the CLI |
| Other docs give their own, hand-derived closures (doc_5 -> exactly 4 memories) | `test_other_docs_have_their_own_hand_derived_closures` | yes (derived by hand from read sets) |
| A doc nothing read quarantines nothing | `test_flagging_a_doc_nothing_read_quarantines_nothing` | yes |
| A fact heals only with >= 2 clean episodes (boundary: exactly 1 does not), and takes the clean majority claim | `test_heal_needs_two_clean_episodes_and_takes_the_clean_majority` | yes (flags doc_2, hand-derived: f_http_usage 1 clean, f_http_client 3 clean -> `requests`) |
| The page shows 6 / 25 / 19 before and after healing; twins are detected by SUPERSEDES | `test_page_numbers_match_the_demo_before_and_after_healing` | via the page data |
| The page server refuses non-loopback Host headers | `test_server_refuses_non_loopback_host_header` | yes |
| Rework refuses any quarantined or nonexistent read, even after a heal | `test_rework_refuses_any_quarantined_or_missing_read_even_after_a_heal` | yes |
| Heal takes a strict plurality (>= 2) and counts only agreeing episodes; ties and lone sources stay red | `test_heal_takes_a_strict_plurality_and_counts_only_agreeing_episodes` | yes (synthetic facts) |
| A dead process cannot close a task; only the author can claim; a retried rework does not duplicate | `test_zombie_complete_cannot_close_a_task_and_rework_is_idempotent` | yes |
| Two advisories and unscripted docs do not crash the CLI or page; receipts go to the doc a memory reaches | `test_two_advisories_and_unscripted_docs_do_not_crash_the_cli_or_page` | yes |

## Manual checks (the human part: do these before recording)

1. `uv run python web/server.py`, open http://localhost:8765, then `uv run quarantine session1 --slow 0.4`: chips appear in five columns. `flag doc_7`: red ink spills along the ribbons and six chips turn red one by one, counters read 6 / 25 / 19. Click `a_requirements`: a yellow highlighter path runs back to doc_7. `session2`: green twins appear under their originals.
2. Projector test: counters readable from 3 m. Quarantined memories have `!` labels; healed twins have `+` labels; flagged documents have `!` labels. Check these cues on the actual recording setup; browser emulation is not a physical projector test.
3. Reset between takes: `uv run quarantine session1` rebuilds the graph from the fixture. Confirm twins, status markers, selected receipt and yellow highlighter path all clear. A delayed receipt response must not restore the old path.
4. Say the numbers from the terminal, never from memory.

## Known limits (say them in the README, do not hide them)

- Agents are scripted: outputs are fixture text, read sets are real captured edges. No LLM on the hero path.
- Read sets are the per-write lists in `fixture.yaml`, not an agent's whole accumulated context. The independent review reported that counting accumulated context would give a closure of 9, not 6. Say "read set of the write", not "everything the agent ever saw".
- Each memory, its authorship and its read-set edges are written in one statement (`loader._memory`); `s1.complete` marks the end of Session 1, and `flag` refuses a graph without it.
- The kill-Planner beat is a real `kill -9` of a separate process; the "new Planner" is the CLI process itself in session s2b.
- Healing is a majority vote over clean episodes, not semantic reasoning.
- One graph per crew. The closure and receipt are unbounded (the graph is a DAG; a 10-hop cap was removed, see `docs/EVAL-HELDOUT.md`).
- FalkorDB 6.0.2 limits we hit (see `spikes/day1-results.txt`): no `EXISTS {}`, `shortestPath` only in WITH/RETURN, no `CREATE (n $props)`.


## Ten worlds and ten environments

- `uv run python scripts/ten_worlds.py` (about 40 s): drives the real CLI (`session1`, `flag`, `unflag`, `session2`, `status`) on ten different worlds (the demo, the support crew, six generated crews of different shapes, a wide fan-out, a dissent-heavy world). For every document: the red set must equal the independent oracle, `session2` must reach a fixpoint with every task done and the three audits at 0, `unflag` must return to zero red; pairs of documents must give the oracle's union.
- `scripts/env_matrix.sh` (about 25 minutes, mostly the mutation check): fresh clones of the committed HEAD in ten environments, three Python versions (3.12, 3.13, 3.14), each with its own throwaway FalkorDB: pytest on all three versions, the ten worlds on all three, the counterfactual and held-out evaluations, the demo path, and the mutation check. Prints one PASS or FAIL line per environment and where its log is.
