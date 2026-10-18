# Team split: Quarantine (set Thu 2026-10-15)

Deadline Sun 2026-10-18 14:29 EDT; submit target Sun 12:00 EDT.

## Status Sun 2026-10-18

| item | state |
|---|---|
| tests | all passed in a fresh GitHub clone run by Parth with Claude on Oct 18; commands and results in `docs/RUNS.md` |
| Aashna | reported on Windows twice (Oct 16 zip; Oct 18 branch `improve` at e92cd46). Her seven defects were fixed. The code review (checklist section 4) and merge decision were not done by a second person |
| Aman | rewrote the README (commit 21c94f2, Oct 17) and edited it again that evening (591bbd2). The blog draft and submission text were drafted by Parth with Claude; Aman can edit them |
| merge rule | Parth pushed `improve` to `main` himself, so the rule below (Aashna reviews first) was not followed |
| live deployment | none; the README gives the complete local setup |
| video | Parth records it on Oct 18; the link goes into the README before submitting |
| repository | public since Oct 18 (an anonymous clone passed all tests; see `docs/RUNS.md`) |

## Status Thu 09:40 (historical)

| item | state |
|---|---|
| fixture, loader, core queries | done |
| CLI: `session1 --slow`, `flag`, `session2 [--kill-planner]` | done; kill-planner rehearsed end to end (rounds [1, 2, 2, 0]) |
| page (`uv run python web/server.py`, http://localhost:8765) | v1 worked: counters 6 / 25 / 19 frozen at flag time, red wave, green replacements, click a red node to see the receipt path |
| page test (`tests/test_web.py`) | done |
| README body, LICENSE, disclosure, MCP bridge, compose file | done since (see README) |
| live deployment, MCP beat in the video, video, blog, submission | not done then: `docs/CHECKLIST-AASHNA.md` and `docs/CHECKLIST-AMAN.md` list the steps |

## Who does what (re-split Fri 2026-10-16 by Parth)

| person | role | owns | first task |
|---|---|---|---|
| **Parth** | build | the page, the CLI, new features, the video; works on branch `improve` with Claude; the `freeze-v1` tag is the fallback | finish the video script with the four answer shapes and the hatched ochre "what a naive wipe loses" views |
| **Aashna** | review, fixes, testing | was to review every commit on `improve` before it merged to `main` (that second-person review was not completed); runs `uv run pytest -q` (0 failed), `scripts/validate.sh`, `scripts/mutation_check.py`, `scripts/heldout_eval.py`, `scripts/counterfactual_eval.py`; tries `quarantine unflag doc_7` (retract a false alarm); owns the fresh-clone run on her laptop and the compose check; files bugs as failing tests | fresh clone and full validation on her machine; then review `quarantine/answers.py` against `docs/GUIDELINE-CONFORMANCE.md` |
| **Aman** | research and writing | README body, LICENSE, AI-use disclosure, rules compliance ("source-available (SSPL)", new work in the window, team locks at submit), the blog post, the submission form; reads the organizers' guide and the FalkorDB docs so README claims cite a source | read `docs/GUIDELINE-CONFORMANCE.md` and `docs/EVAL-HELDOUT.md`; draft the README sections that cite them; check the kickoff email's guide text against our paraphrase |

Merge rule: nothing lands on `main` without Aashna's review and a green `scripts/validate.sh`. Parth does not merge his own branch. (Not followed on Oct 17 and 18; see the status above.)

## Checkpoints (EDT)

- **D1 Thu 20:00**: `session1` -> `flag doc_7` -> page shows six red, numbers match the test. (True on Parth's laptop; Aashna and Aman had not reproduced it by D1.)
- **D2 Fri 20:00**: full run on the VM, video take 1, cut-list decisions. Feature freeze Fri 21:30. (No VM run is recorded; see `docs/VALIDATION.md`.)
- **D3 Sat 19:00**: submittable: repo public-ready, README numbers = test numbers, video 3:00 or less and unlisted, form dry run.
- **Sun 10:30 to 11:30**: submit. Sun 12:00 to 14:29: hold; fix only a broken link.
