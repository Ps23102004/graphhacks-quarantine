# VALIDATION — status of the Quarantine build (Helix-style)

Updated Fri 2026-10-16 (branch `improve`; `freeze-v1` tag = the Thursday baseline). Re-fill the "status" column after every change; do not record a pass you did not just see.

| field | value |
|---|---|
| repo | `~/Developer/graphhacks-quarantine` (local, no remote yet) |
| commit validated | see `git log -1`; `scripts/validate.sh` validates committed HEAD only |
| problem statement | when one ingested document is found prompt-injected, quarantine exactly the memories it influenced across agents and sessions, explain each with a path, heal facts that still have clean support, and redo only the poisoned work in dependency order |
| image | `falkordb/falkordb:6.0.2@sha256:107455e8...` (source-available, SSPL) |

## Test results

| check | command | result |
|---|---|---|
| unit + integration | `uv run pytest -q` | 52 passed |
| fresh clone, throwaway FalkorDB, real CLI + page | `scripts/validate.sh` | not re-run since the guide changes: run before merging `improve` |
| mutation check (tests catch breakage) | `uv run python scripts/mutation_check.py` | 30 mutations; last full run pending (see below) |
| held-out worlds vs independent oracle | `uv run python scripts/heldout_eval.py` | 3 x 2645 cases, 0 mismatches; 3 x 878 full-pipeline runs, 0 violations (`docs/EVAL-HELDOUT.md`) |
| organizers' guide + Track 02 bar | `uv run pytest -q tests/test_guideline.py tests/test_track02_bar.py` | 12 passed (`docs/GUIDELINE-CONFORMANCE.md`) |
| independent review (different model, read-only, did not write the code) | Opus 5.5 subagent, 2026-10-15 | 14 findings (2 blockers, 8 should-fix, 4 nits); see below |

"Fail-to-pass" evidence: each new test was written against the unfixed behaviour the reviewer reported (or against a surviving mutant) and the mutation check shows it goes red when the fix is removed.

## Review findings and what happened

| # | finding | status |
|---|---|---|
| 1 blocker | rework guard allowed citing poisoned memory once it had a replacement | fixed (refuses any quarantined read), tested, mutation-checked |
| 2 blocker | a nonexistent read id silently dropped provenance | fixed (refuses missing ids), tested, mutation-checked |
| 3 | COMPLETE not tied to session, lease or replacement (zombie deadlocks the Coder) | fixed, tested, mutation-checked |
| 4 | heal majority: wrong support count, alphabetical tie-break | fixed (strict plurality >= 2, support = agreeing episodes; same rule in `healable`), tested, mutation-checked |
| 5 | rework not idempotent | fixed, tested, mutation-checked |
| 6 | CLI/page crash on a doc with no episodes (null t0) | fixed, tested |
| 7 | CLI crash on a second flagged doc | fixed, tested |
| 8 | `session2` KeyError on docs without scripted rework | fixed (clear exit message), tested |
| 9 | page assumes one flagged doc | fixed: counters only when exactly one advisory; receipts go to the doc the memory reaches; tested |
| 10 | CLI counters changed on re-flag | fixed (baselines exclude healed twins everywhere), tested |
| 11 | dead `is None` check in `receipt()` | fixed |
| 12 | any agent could claim any task | fixed (author only), tested, mutation-checked. Lease boundary is inclusive (a 5-tick lease covers 6 ticks): documented, not changed |
| 13 | receipt has two tied shortest paths | test now accepts both valid receipts; demo script says not to promise which |
| 14 | reading a missing graph creates it; closure depth cap is silent | **open**: mistyped `--graph` creates an empty graph; depth is 10 (documented in limits) |

Demo-script mismatches the reviewer found (wrong `--slow` usage, nodes not appearing live, wording of log lines, GRAPH.LIST, simulated kill) are fixed: `session1` now prints and the page fills as each memory is written, the kill-Planner beat is a real SIGKILL of a separate process, and `docs/DEMO-SCRIPT.md` is captured from real output.

## Demo-verification continuation — 2026-10-15

Working-tree checks on `fix/demo-verification`, based on `26d2f7f`; these changes are not committed. Tests used a separate pinned-image FalkorDB container on loopback port 6391 and a page server on 8766. The existing demo database was not changed.

- Python suite: **52 passed**. JavaScript syntax and diff whitespace checks passed.
- `scripts/check_browser.js`: **11 passed** through the standalone Playwright CLI, including the fully healed graph's insertion and resize checks. The original eight checks also ran through Playwright MCP. The standalone runner initially lacked a global `URL`; resolving the origin inside the page fixed that test-only compatibility issue.
- Live CLI replay: precise/per-agent/time-based **6 / 25 / 19**, a four-hop clicked receipt, actual Planner SIGKILL with exit **-9**, refusal while its lease was live, takeover after expiry, rounds **[1, 2, 2, 0]**, and **28 memories** after healing.
- Visible Chromium tab: the post-fix wave counted **0, 1, 2, 3, 4, 5, 6**, with **418–420 ms** between steps. Document visibility remained `visible`. This verifies that browser session, not an OS-level foreground recording or physical projector.
- Captured and visually inspected **1920x1080** and **960x1080** views, including achromatopsia emulation. `!` labels and dashed borders identify quarantined memories; `+` labels identify healed twins; flagged sources also have `!` labels. Artifact text uses dark ink on status fills. This is not a full accessibility audit.
- Fixed reset leaving a stale receipt, orange path and selection. A request token also rejects receipt responses that arrive after reset or a newer click. Browser regressions failed before these fixes and passed afterward.
- Fixed persistent clipping of the fully healed graph on resize. The library's automatic camera scaling could leave documents or the healed artifact offscreen. The page now refits on the next animation frame after the network's resize event. Tests wait for actual canvas backing-buffer dimensions, not just CSS width; both healed resize cases failed before the fix and passed afterward. Final screenshots show every node at both sizes.
- Independent read-only Opus review inspected the status/reset UI changes and browser test and found no high-confidence correctness issues. It checked syntax and whitespace but did not execute browser tests. The CLI compatibility correction, stronger geometry checks and final resize handler came afterward. Those were verified through failing-then-passing regressions and the full suite, not a second independent review.
- Evidence screenshots and CLI logs: `/tmp/quarantine-qa-20261015/`.

The fresh-clone and mutation results above are inherited from the earlier session, not new runs against these uncommitted changes. Graph queries, fixture, loader and CLI were unchanged.

## Not yet verified (do before the video)

- Physical projector, actual recording setup, and screen-reader/keyboard accessibility.
- Fresh clone on a second person's laptop (Aashna or Aman), including `docker run` of the pinned image on their architecture (amd64 digest not re-checked).
- Deployment (VM), MCP beat, README body, LICENSE, AI-use disclosure, blog, submission form: not started.
- Colour-blind usability with people: grayscale browser emulation and non-colour cues were checked, but this is not a substitute for user testing.
