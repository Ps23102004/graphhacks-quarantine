# Team split — Quarantine (set Thu 2026-10-15)

Deadline Sun 2026-10-18 14:29 EDT; submit target Sun 12:00 EDT.

## Status Thu 09:40 (done, all tests green: `uv run pytest -q`)

| item | state |
|---|---|
| fixture, loader, 15 verified queries | done |
| CLI: `session1 --slow`, `flag`, `session2 [--kill-planner]` | done, kill-planner rehearsed end to end (rounds [1, 2, 2, 0]) |
| red-wave page (`uv run python web/server.py`, http://localhost:8765) | v1 works: counters 6 / 25 / 19 frozen at flag time, red wave, green twins, click a red node -> receipt path |
| page test (`tests/test_web.py`) | done |
| README body, LICENSE, disclosure, MCP bridge, compose file | done since (see README) |
| live deployment, MCP beat in the video, video, blog, submission | not done yet: `docs/CHECKLIST-AASHNA.md` (fresh clone, tests, review) and `docs/CHECKLIST-AMAN.md` (README, blog, submission) list the steps |

## Who does what (re-split Fri 2026-10-16 by Parth)

| person | role | owns | first task |
|---|---|---|---|
| **Parth** | build: adding things | the page, the CLI, new features, the video; works on branch `improve` with Claude; `freeze-v1` tag is the fallback | finish the video script with the four answer shapes and the hatched ochre "what a naive wipe loses" views |
| **Aashna** | review, fixes, testing | reviews every commit on `improve` before it merges to main; runs `uv run pytest -q` (0 failed), `scripts/validate.sh`, `scripts/mutation_check.py`, `scripts/heldout_eval.py`, `scripts/counterfactual_eval.py` (all exist); tries `quarantine unflag doc_7` (retract a false alarm); owns the fresh-clone run on her laptop and the compose check; files bugs as failing tests | fresh clone + full validation on her machine; then review `quarantine/answers.py` against `docs/GUIDELINE-CONFORMANCE.md` |
| **Aman** | research and paper work | README body, LICENSE, AI-use disclosure, rules compliance ("source-available (SSPL)", new work in window, team locks at submit), the blog post, the submission form; researches the organizers' guide and FalkorDB docs so every claim in the README cites something | read `docs/GUIDELINE-CONFORMANCE.md` and `docs/EVAL-HELDOUT.md`; draft the README sections that cite them; confirm the kickoff email's guide text against our paraphrase |

Merge rule: nothing lands on `main` without Aashna's review and a green `scripts/validate.sh`. Parth does not merge his own branch.

## Checkpoints (EDT)

- **D1 Thu 20:00**: `session1` -> `flag doc_7` -> page shows six red, numbers match the test. (Already true on Parth's laptop; D1 is Aashna and Aman reproducing it.)
- **D2 Fri 20:00**: full run on the VM, video take 1, cut-list decisions. Feature freeze Fri 21:30.
- **D3 Sat 19:00**: submittable: repo public-ready, README numbers = test numbers, video <= 3:00 unlisted, form dry run.
- **Sun 10:30-11:30**: submit. Sun 12:00-14:29: hold, fix only a broken link or a dead VM.
