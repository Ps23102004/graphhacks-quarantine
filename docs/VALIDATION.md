# Validation: status of the Quarantine build

Rows below were last filled on Sun 2026-10-18; the commit each was run on is in `docs/RUNS.md`. The `freeze-v1` tag is the Thursday baseline. Re-fill the "result" column after every change, and do not record a pass you did not just see.

| field | value |
|---|---|
| repo | `~/Developer/graphhacks-quarantine` (GitHub: `Ps23102004/graphhacks-quarantine`) |
| commit validated | see `git log -1`. `scripts/validate.sh` copies the working tree, uncommitted edits included, so run it on a clean tree to validate a commit |
| problem statement | when one ingested document is flagged as prompt-injected, quarantine every memory whose recorded reads reach it, across agents and sessions; explain each one with a path; heal facts that still have clean support; and redo the quarantined work in dependency order. The closure is provenance-level: about 63% of flags on random worlds would not have changed, and influence that was never recorded as a read is missed (see `docs/COUNTERFACTUAL.md`) |
| image | `falkordb/falkordb:6.0.2@sha256:107455e8...` (source-available, SSPL) |

## Test results

| check | command | result |
|---|---|---|
| unit + integration | `uv run pytest -q` | all passed, 0 failed at the last full run (not re-run on 2026-10-18 for this doc). The count changes; read it from pytest's summary line, see `docs/TESTING.md` |
| working-tree copy, throwaway FalkorDB, real CLI + page | `scripts/validate.sh` | all passed, 0 failed at the last run (not re-run on 2026-10-18 for this doc) |
| mutation check (tests catch breakage) | `uv run python scripts/mutation_check.py` | run on `3874be2` (Python 3.13), 2026-10-18: 0 unexpected survivor(s) of 32 mutations (30 caught, 2 equivalent mutants survived); output in `docs/RUNS.md` |
| held-out worlds vs independent oracle | `uv run python scripts/heldout_eval.py` | re-run on `b31ba1e`, 2026-10-18: 3 x 2,645 cases, 0 mismatches; 3 x 878 full-pipeline runs, 0 violations (`docs/EVAL-HELDOUT.md`) |
| counterfactual replay | `uv run python scripts/counterfactual_eval.py --worlds 20` | re-run on `b31ba1e`, 2026-10-18: 0 false negatives, invented receipts, wrong clean answers and page mismatches on the three gated models; the unrecorded-influence model missed 9% (`docs/COUNTERFACTUAL.md`) |
| organizers' guide + Track 02 bar | `uv run pytest -q tests/test_guideline.py tests/test_track02_bar.py` | re-run on `b31ba1e`, 2026-10-18: 12 passed. These tests were tightened after a skeptic review on 2026-10-16 (`docs/GUIDELINE-CONFORMANCE.md`) |
| independent review (different model, read-only, did not write the code) | Opus 5.5 subagent, 2026-10-15 | 14 findings (2 blockers, 8 should-fix, 4 nits); see below |

Fail-to-pass evidence: each new test was written against the unfixed behaviour the reviewer reported, or against a surviving mutant. For the findings marked "mutation-checked" below, the mutation check also shows the test goes red when the fix is removed.

## Review findings and what happened

| # | finding | status |
|---|---|---|
| 1 blocker | rework guard allowed citing poisoned memory once it had a replacement | fixed (refuses any quarantined read), tested, mutation-checked |
| 2 blocker | a nonexistent read id silently dropped provenance | fixed (refuses missing ids), tested, mutation-checked |
| 3 | COMPLETE not tied to session, lease or replacement (a zombie process deadlocks the Coder) | fixed, tested, mutation-checked |
| 4 | heal majority: wrong support count, alphabetical tie-break | fixed (strict plurality >= 2, support = agreeing episodes; same rule in `healable`), tested, mutation-checked |
| 5 | rework not idempotent | fixed, tested. An idempotence mutant existed until commit `9ff88d0`; the current `MUTATIONS` list has none |
| 6 | CLI and page crash on a doc with no episodes (null t0) | fixed, tested |
| 7 | CLI crash on a second flagged doc | fixed, tested |
| 8 | `session2` KeyError on docs without scripted rework | fixed, tested. First fix was a clear exit message; now `session2` derives the rework from the graph (`loader.derive_rework`) and marks the twin `needs_regeneration` |
| 9 | page assumes one flagged doc | fixed: counters only when there is exactly one advisory; receipts go to the doc the memory reaches; tested |
| 10 | CLI counters changed on re-flag | fixed (baselines exclude healed twins everywhere), tested |
| 11 | dead `is None` check in `receipt()` | fixed |
| 12 | any agent could claim any task | fixed (author only), tested, mutation-checked. The lease boundary is inclusive (a 5-tick lease covers 6 ticks): documented, not changed |
| 13 | receipt has two tied shortest paths | the test accepts both valid receipts; the demo script says not to promise which one appears |
| 14 | reading a missing graph creates it; closure depth cap is silent | closure depth: fixed (no hop bound, regression test on a 40-step chain, see `docs/EVAL-HELDOUT.md`). Mistyped `--graph`: fixed (`flag`, `unflag`, `session2` and `status` refuse a graph that does not exist and create none) |

The reviewer also found mismatches between the demo script and the real run: wrong `--slow` usage, nodes not appearing live, log-line wording, GRAPH.LIST, and a simulated kill. All are fixed. `session1` now prints each memory and the page fills as it is written. The kill-Planner beat is a real SIGKILL of a separate process. `docs/DEMO-SCRIPT.md` is captured from real output.

## Demo-verification pass, 2026-10-15 (historical)

This section describes the earlier vis-network page. The light editorial ledger (`DESIGN.md`) has replaced it, so the UI details below (dashed borders, orange path, camera scaling, canvas resize) no longer describe the shipped page.

The checks ran on the working tree of `fix/demo-verification`, based on `26d2f7f`, before those changes were committed. They used a separate pinned-image FalkorDB container on loopback port 6391 and a page server on 8766. The demo database was not changed.

- Python suite: all passed at that commit. JavaScript syntax and diff whitespace checks passed.
- `scripts/check_browser.js`: **11 passed** through the standalone Playwright CLI, including insertion and resize checks on the fully healed graph. The first eight checks also ran through Playwright MCP. The standalone runner lacked a global `URL` at first; resolving the origin inside the page fixed that test-only issue.
- Live CLI replay: quarantine / wipe agents / roll back **6 / 25 / 19**, a four-hop clicked receipt, a real Planner SIGKILL with exit **-9**, refusal while its lease was live, takeover after expiry, rounds **[1, 2, 2, 0]**, and **28 memories** after healing.
- Visible Chromium tab: the wave counted **0, 1, 2, 3, 4, 5, 6**, with **418 to 420 ms** between steps, and the document stayed `visible`. This verifies that browser session, not an OS-level recording or a physical projector.
- Captured and inspected **1920x1080** and **960x1080** views, including achromatopsia emulation. `!` labels and dashed borders marked quarantined memories, `+` labels marked healed twins, and flagged sources also had `!` labels. Artifact text used dark ink on status fills. This was not a full accessibility audit.
- Fixed: reset left a stale receipt, orange path and selection. A request token now also rejects receipt responses that arrive after a reset or a newer click. The browser regressions failed before these fixes and passed after.
- Fixed: the fully healed graph stayed clipped after a resize, because the library's automatic camera scaling could leave documents or the healed artifact offscreen. The page refit on the next animation frame after the resize event. The tests waited for real canvas backing-buffer sizes, not just CSS width. Both healed resize cases failed before the fix and passed after.
- An independent read-only Opus review of the status/reset UI changes and the browser test found no high-confidence correctness issues. It checked syntax and whitespace but did not run the browser tests. The later CLI compatibility fix, stronger geometry checks and final resize handler were verified by failing-then-passing regressions and the full suite, not by a second review.
- Screenshots and CLI logs from that pass are on the original machine only, in `/tmp/quarantine-qa-20261015/`.

The graph queries, fixture, loader and CLI did not change in that pass.

## Not yet verified (do before the video)

- Physical projector, the actual recording setup, and screen-reader and keyboard accessibility with real users.
- Aashna ran branch `improve` at e92cd46 on Windows; nobody other than Parth has run the final commit. The pinned image's amd64 digest was not re-checked.
- Live deployment (VM), the MCP beat in the video, and the submission form: not done. A blog draft (`docs/BLOG.md`), submission text (`docs/SUBMISSION.md`), the README, LICENSE and the AI-use disclosure exist; see `docs/CHECKLIST-AASHNA.md` and `docs/CHECKLIST-AMAN.md`.
- Colour-blind usability with people. Grayscale browser emulation and non-colour cues were checked, but that does not replace user testing.
