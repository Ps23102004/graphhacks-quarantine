# VALIDATION — status of the Quarantine build (Helix-style)

Updated Thu 2026-10-15. Re-fill the "status" column after every change; do not record a pass you did not just see.

| field | value |
|---|---|
| repo | `~/Developer/graphhacks-quarantine` (local, no remote yet) |
| commit validated | see `git log -1`; `scripts/validate.sh` validates committed HEAD only |
| problem statement | when one ingested document is found prompt-injected, quarantine exactly the memories it influenced across agents and sessions, explain each with a path, heal facts that still have clean support, and redo only the poisoned work in dependency order |
| image | `falkordb/falkordb:6.0.2@sha256:107455e8...` (source-available, SSPL) |

## Test results

| check | command | result |
|---|---|---|
| unit + integration | `uv run pytest -q` | 18 passed |
| fresh clone, throwaway FalkorDB, real CLI + page | `scripts/validate.sh` | 22 passed, 0 failed |
| mutation check (tests catch breakage) | `uv run python scripts/mutation_check.py` | 22 mutations, 0 unexpected survivors; 1 documented equivalent mutant (redundant size check in the heal query) |
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

## Not yet verified (do before the video)

- Page, checked by eye in the in-app browser on 2026-10-15: nodes fill in live during `session1 --slow 0.4`; red wave counter climbs 0 -> 6 as nodes turn red; reset (`session1`) clears twins, red state and timers. NOT checked: timing smoothness in a foreground window (the in-app tab throttled timers, so steps arrived in uneven pairs), the red wave on a projector or the recording setup, and the layout at 1920x1080 (checked at 800x955 only).
- Fresh clone on a second person's laptop (Aashna or Aman), including `docker run` of the pinned image on their architecture (amd64 digest not re-checked).
- Deployment (VM), MCP beat, README body, LICENSE, AI-use disclosure, blog, submission form: not started.
- Colour-blind legibility of red vs grey nodes.
