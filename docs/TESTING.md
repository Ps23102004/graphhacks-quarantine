# Testing: how to know Quarantine works

There are several layers, from fastest to most convincing. Anyone on the team, or a judge, can run all of them.

## 0. Prerequisites

- Docker running, `uv` installed (https://docs.astral.sh/uv/), Python 3.12 or newer (`requires-python = ">=3.12"` in `pyproject.toml`).
- FalkorDB 6.0.2, pinned by digest. FalkorDB is source-available (SSPL), not open source.

```bash
docker run -d --name quarantine-falkordb -p 127.0.0.1:6379:6379 -p 127.0.0.1:3000:3000 \
  falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
uv sync --all-extras                      # --all-extras installs the optional MCP SDK the MCP tests need
```

## 1. Unit and integration tests

```bash
uv run pytest -q          # expect: all tests pass, 0 failed
```

The number of tests changes as tests are added. Counts in dated status lines are historical; read the current count from pytest's summary line.

The tests use their own graphs and delete them afterwards. None of them is named `quarantine`, so they never touch the demo graph.

## 2. Working-tree validation: close to what a stranger would see

```bash
scripts/validate.sh       # expect: "validation: N passed, 0 failed" (N changes as checks are added)
```

What it does:

- copies the working tree, uncommitted edits included, into a temp dir (`.git`, `.venv`, `.pytest_cache`, `dist` and `build` are left out);
- starts a throwaway FalkorDB on port 6390 and installs from the lockfile (`uv sync --frozen --all-extras`);
- runs pytest;
- runs the real CLI and checks the exact lines the demo shows: 6 vs 25 vs 19, the six memories, the 4-hop receipt, the heal to `requests`, the kill-Planner takeover, rounds `[1, 2, 2, 0]`, and the control closure for `doc_5`;
- builds the wheel, lists and calls the MCP tools, and checks `docker compose config`;
- checks the page JSON, and that the page refuses a foreign `Host` header and a `POST`.

Because it copies the working tree, it is not a fresh clone. To validate a commit, run it on a clean tree (`git status` empty). It cannot catch a needed file that was never committed.

## 3. Mutation check: do the tests catch breakage

```bash
uv run python scripts/mutation_check.py     # expect: "0 unexpected survivor(s) of N mutations"
```

This is slow: one pytest run per mutation. It breaks one thing at a time in a throwaway clone of the committed HEAD, against its own FalkorDB on port 6391. pytest must go red each time. The `MUTATIONS` list in `scripts/mutation_check.py` covers:

- closure edge types and hop bounds, in both `FLAG_AND_CLOSE` and `TAINT_CLOSURE`;
- the heal threshold and tie rule, and episodes becoming healable;
- rework blockers, the rework guard (quarantined, missing and empty reads), dead reads in derived rework, and the author and session fences;
- lease expiry and live holder, claim ownership, and the `COMPLETE` session and replacement checks;
- both baselines (bounds, healed twins, an off-by-one tick);
- one fixture read set, the receipt's hop bound, and the page's twin detection.

A mutant whose name says "equivalent mutant" changes a guard that another check already covers. It may survive and is not counted as a failure. The current list has two: the heal query's own `>= 2` check and its own tie check (both covered by the `healable` flag).

## 4. Browser regressions (optional, needs the Playwright CLI)

Start the page against a graph already seeded with `quarantine session1`. With the Playwright CLI and Chrome installed:

```bash
playwright-cli -s=quarantine-ui-check open http://localhost:8765 --browser chrome
playwright-cli -s=quarantine-ui-check run-code --filename scripts/check_browser.js
playwright-cli -s=quarantine-ui-check close
```

Expect every check to report `passed: true`. The script loads the real ledger page (no chart library) and replaces only the `/graph` and `/receipt` responses, so it never writes to FalkorDB. Among other things it checks:

- every cell stays visible at 1920 and 960 px, and at 375 px there is no horizontal scroll;
- the quarantine counter climbs to 6 with the red wave;
- non-colour markers: `!` on quarantined memories and the flagged source, `+` on healed twins;
- the receipt highlights four arcs and reads as a sentence;
- the time-based view paints 13 clean casualties and the per-agent view 19;
- a cell can be selected from the keyboard;
- reset clears the receipt, the highlight, twins and markers, and a receipt that arrives after reset is ignored;
- two advisories, partial unflag, placeholder twins and an empty graph.

It supplements the live CLI run. It does not prove the graph queries or process recovery. The Python suite does not need Playwright.

## What each claim is tested by

| claim (what the video says) | test | independent of the fixture's tuning |
|---|---|---|
| Fixture is well formed; read sets only point backwards in time | `test_fixture_loads_and_is_consistent` | yes (audit queries) |
| Flagging doc_7 quarantines 6; per-agent wipe would hit 25; time-based 19 | `test_closure_is_precise_and_baselines_are_not` | no: the numbers come from the fixture's `expected:` block |
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

All are in `tests/test_quarantine.py` except the two page tests, which are in `tests/test_web.py`.

## Manual checks (the human part: do these before recording)

1. Run `uv run python web/server.py`, open http://localhost:8765, then run `uv run quarantine session1 --slow 0.4`. Chips appear in five columns. Run `uv run quarantine flag doc_7`: red ink spreads along the ribbons, six chips turn red one by one, and the counters read 6 / 25 / 19. Click `a_requirements`: a yellow highlighter path runs back to doc_7. Run `uv run quarantine session2`: green twins appear under their originals.
2. Projector test: the counters must be readable from 3 m. Quarantined memories and flagged documents have `!` labels; healed twins have `+` labels. Check these cues on the actual recording setup. Browser emulation is not a physical projector test.
3. Reset between takes: `uv run quarantine session1` rebuilds the graph from the fixture. Confirm that twins, status markers, the selected receipt and the yellow path all clear. A delayed receipt response must not bring the old path back.
4. Read the numbers from the terminal, never from memory.

## Known limits (say them in the README, do not hide them)

- Agents are scripted: their outputs are fixture text, and their read sets come from the fixture and are stored as real edges. No LLM is on the demo path.
- Read sets are the per-write lists in `fixture.yaml`, not an agent's whole accumulated context. If each step and artifact also counted everything its author read or wrote before, the demo closure would be 9 memories, not 6 (the independent review reported this; `worldgen._make_cumulative` on the fixture gives the same 9). Say "read set of the write", not "everything the agent ever saw".
- Each memory, its authorship and its read-set edges are written in one statement (`loader._memory`). At the end of Session 1 the `s1` Session node gets `complete = true`, and `flag` refuses a graph without it.
- The kill-Planner beat is a real `kill -9` of a separate process. The "new Planner" is the CLI process itself, in session `s2b`.
- Healing is a majority vote over clean episodes, not semantic reasoning.
- One graph per crew. The closure and receipt have no hop bound (the graph is a DAG; a 10-hop cap was removed, see `docs/EVAL-HELDOUT.md`).
- FalkorDB 6.0.2 limits we hit: no `EXISTS {}`, and `shortestPath` only in `WITH` or `RETURN` (both in `spikes/day1-results.txt`); no `CREATE (n $props)` (the server answers "Encountered unhandled type in inlined properties").

## Ten worlds and ten environments

- `uv run python scripts/ten_worlds.py` drives the real CLI (`session1`, `flag`, `unflag`, `session2`, `status`) on ten worlds: the demo, the support crew, five generated crews of different shapes, a 25-step chain, a wide fan-out and a dissent-heavy world. For every document, the red set must equal the independent oracle, `session2` must reach a fixpoint with every task done and the three audits at 0, and `unflag` must return to zero red. Pairs of documents must give the oracle's union.
- `scripts/env_matrix.sh` runs fresh clones of the committed HEAD in ten environments across Python 3.12, 3.13 and 3.14, each with its own throwaway FalkorDB: pytest on all three versions, the ten worlds on all three, the counterfactual evaluation (30 worlds), the held-out evaluation (40 worlds, 10 pipeline worlds), the demo path and the mutation check. It prints one PASS or FAIL line per environment, with the log path for each failure. The mutation check takes most of the time.

Run one pytest at a time against a given FalkorDB: several tests use fixed graph names (for example `quarantine_web_test`), so two concurrent runs can collide and fail.
