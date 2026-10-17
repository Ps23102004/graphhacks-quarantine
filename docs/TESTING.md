# TESTING — how to know Quarantine works

Three layers, from fastest to most convincing. Anyone on the team (or a judge) can run all of them.

## 0. Prerequisites

- Docker running, `uv` installed (https://docs.astral.sh/uv/), Python 3.12+.
- FalkorDB 6.0.2 pinned by digest. FalkorDB is source-available (SSPL), not open source.

```bash
docker run -d --name quarantine-falkordb -p 6379:6379 -p 3000:3000 \
  falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
uv sync --all-extras                      # --all-extras installs the optional MCP SDK the MCP tests need
```

## 1. Unit and integration tests (about 5 s)

```bash
uv run pytest -q          # expect: 52 passed
```

Tests use their own graphs (`quarantine_test`, `quarantine_cli_test`, `quarantine_web_test`) and delete them afterwards. They never touch the demo graph named `quarantine`.

## 2. Fresh-clone validation (about 1 min): what a stranger would see

```bash
scripts/validate.sh       # expect: "validation: 22 passed, 0 failed"
```

Clones the committed HEAD into a temp dir, starts a throwaway FalkorDB on :6390, installs from the lockfile, runs pytest, then runs the real CLI and checks the exact lines the video says (6 vs 25 vs 19, the receipt, the heal, the kill-Planner takeover, the control closure for doc_5, the page JSON and its Host check). Uncommitted work is not validated: commit first.

## 3. Mutation check (about 3 min): do the tests actually catch breakage?

```bash
uv run python scripts/mutation_check.py     # expect: "0 unexpected survivor(s)"
```

Breaks one thing at a time in a throwaway clone (22 mutations: closure edge types and depth, heal threshold and tie rule, episodes healable, blockers, lease expiry and holder, claim ownership, COMPLETE session and replacement checks, rework guard and idempotence, baselines, a fixture read set, page counters, twin detection, receipts). pytest must go red each time. One documented equivalent mutant survives (the heal query's `clean_total >= 2` duplicates the `healable` flag guard).

## 4. Browser regressions (optional, installed Playwright CLI)

Start the page against a graph already seeded with `quarantine session1`. With Playwright CLI and Chrome already installed:

```bash
playwright-cli -s=quarantine-ui-check open http://localhost:8765 --browser chrome
playwright-cli -s=quarantine-ui-check run-code --filename scripts/check_browser.js
playwright-cli -s=quarantine-ui-check close
```

Expect 19 checks with `passed: true`. This runs the real hive page (plain SVG, no chart library), substitutes only `/graph` and `/receipt` responses, and never writes to FalkorDB. It covers every cell staying visible at 1920, 960 and 375 px, no horizontal scroll on a phone, the precise counter climbing with the red wave, non-colour markers (`!`, `+`, `×`), the receipt drawing four arcs and reading as a sentence, the two naive-wipe views painting 13 and 19 clean casualties, healed twins fitting, keyboard selection, reset cleanup, and a receipt arriving after reset. It supplements the live CLI run; it does not prove graph queries or process recovery. The Python suite does not require Playwright.

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
| Rework refuses any quarantined or nonexistent read, even after a heal | `test_rework_refuses_any_quarantined_or_missing_read_even_after_a_heal` | yes |
| Heal takes a strict plurality (>= 2) and counts only agreeing episodes; ties and lone sources stay red | `test_heal_takes_a_strict_plurality_and_counts_only_agreeing_episodes` | yes (synthetic facts) |
| A dead process cannot close a task; only the author can claim; a retried rework does not duplicate | `test_zombie_complete_cannot_close_a_task_and_rework_is_idempotent` | yes |
| Two advisories and unscripted docs do not crash the CLI or page; receipts go to the doc a memory reaches | `test_two_advisories_and_unscripted_docs_do_not_crash_the_cli_or_page` | yes |

## Manual checks (the human part: do these before recording)

1. `uv run python web/server.py`, open http://localhost:8765, then `uv run quarantine session1 --slow 0.4`: nodes appear grey. `flag doc_7`: six turn red one by one, counters read 6 / 25 / 19. Click `a_requirements`: orange path to doc_7. `session2`: green twins appear.
2. Projector test: counters readable from 3 m. Quarantined memories have `!` labels and dashed borders; healed twins have `+` labels; flagged documents have `!` labels. Check these cues on the actual recording setup; browser emulation is not a physical projector test.
3. Reset between takes: `uv run quarantine session1` rebuilds the graph from the fixture. Confirm twins, status markers, selected receipt and orange path all clear. A delayed receipt response must not restore the old path.
4. Say the numbers from the terminal, never from memory.

## Known limits (say them in the README, do not hide them)

- Agents are scripted: outputs are fixture text, read sets are real captured edges. No LLM on the hero path.
- Read sets are the per-write lists in `fixture.yaml`, not an agent's whole accumulated context. The independent review reported that counting accumulated context would give a closure of 9, not 6. Say "read set of the write", not "everything the agent ever saw".
- The read set is written as edges right after the memory node, in separate queries, and checked by audit queries; it is not one atomic transaction.
- The kill-Planner beat is a real `kill -9` of a separate process; the "new Planner" is the CLI process itself in session s2b.
- Healing is a majority vote over clean episodes, not semantic reasoning.
- One graph per crew; variable-length traversals are bounded at depth 10.
- FalkorDB 6.0.2 limits we hit (see DAY1-SPIKES.md): no `EXISTS {}`, `shortestPath` only in WITH/RETURN, no `CREATE (n $props)`.
