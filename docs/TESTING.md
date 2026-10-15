# TESTING — how to know Quarantine works

Three layers, from fastest to most convincing. Anyone on the team (or a judge) can run all of them.

## 0. Prerequisites

- Docker running, `uv` installed (https://docs.astral.sh/uv/), Python 3.12+.
- FalkorDB 6.0.2 pinned by digest. FalkorDB is source-available (SSPL), not open source.

```bash
docker run -d --name quarantine-falkordb -p 6379:6379 -p 3000:3000 \
  falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
uv sync
```

## 1. Unit and integration tests (about 5 s)

```bash
uv run pytest -q          # expect: 14 passed
```

Tests use their own graphs (`quarantine_test`, `quarantine_cli_test`, `quarantine_web_test`) and delete them afterwards. They never touch the demo graph named `quarantine`.

## 2. Fresh-clone validation (about 1 min): what a stranger would see

```bash
scripts/validate.sh       # expect: "validation: 21 passed, 0 failed"
```

Clones the committed HEAD into a temp dir, starts a throwaway FalkorDB on :6390, installs from the lockfile, runs pytest, then runs the real CLI and checks the exact lines the video says (6 vs 25 vs 19, the receipt, the heal, the kill-Planner takeover, the control closure for doc_5, the page JSON and its Host check). Uncommitted work is not validated: commit first.

## 3. Mutation check (about 2 min): do the tests actually catch breakage?

```bash
uv run python scripts/mutation_check.py     # expect: "0 unexpected survivor(s)"
```

Breaks one thing at a time in a throwaway clone (closure edge types, depth cap, heal threshold, episodes healable, blockers, lease expiry, lease holder check, rework guard, baselines, a fixture read set, page counters, page twin detection). pytest must go red each time. One documented equivalent mutant survives (the heal query's `clean_total >= 2` duplicates the `healable` flag guard).

## What each claim is tested by

| claim (what the video says) | test | independent of the fixture's tuning? |
|---|---|---|
| Fixture is well formed; read sets only point backwards in time | `test_fixture_loads_and_is_consistent` | yes (audit queries) |
| Flagging doc_7 quarantines exactly 6; per-agent wipe would hit 25; time-based 19 | `test_closure_is_precise_and_baselines_are_not` | numbers come from the fixture's `expected:` block |
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

## Manual checks (the human part: do these before recording)

1. `uv run python web/server.py`, open http://localhost:8765, then `uv run quarantine session1 --slow 0.4`: nodes appear grey. `flag doc_7`: six turn red one by one, counters read 6 / 25 / 19. Click `a_requirements`: orange path to doc_7. `session2`: green twins appear.
2. Projector test: counters readable from 3 m. Known gap: red vs grey differ by colour and brightness only (no pattern or outline), so check it on the real screen and consider a label or outline for colour-blind viewers.
3. Reset between takes: `uv run quarantine session1` rebuilds the graph from the fixture.
4. Say the numbers from the terminal, never from memory.

## Known limits (say them in the README, do not hide them)

- Agents are scripted: outputs are fixture text, read sets are real captured edges. No LLM on the hero path.
- Read-set capture is conservative: any earlier read in the session counts as influence. Precision depends on short scripted steps.
- Healing is a majority vote over clean episodes, not semantic reasoning.
- One graph per crew; variable-length traversals are bounded at depth 10.
- FalkorDB 6.0.2 limits we hit (see DAY1-SPIKES.md): no `EXISTS {}`, `shortestPath` only in WITH/RETURN, no `CREATE (n $props)`.
