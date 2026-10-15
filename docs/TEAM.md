# Team split — Quarantine (set Thu 2026-10-15)

Deadline Sun 2026-10-18 14:29 EDT; submit target Sun 12:00 EDT. Full schedule and cut list: `plans/graphhacks-quarantine/PLAN.md` in the hackathons repo.

## Status Thu 09:40 (done, all tests green: `uv run pytest -q` -> 10 passed)

| item | state |
|---|---|
| fixture, loader, 15 verified queries | done |
| CLI: `session1 --slow`, `flag`, `session2 [--kill-planner]` | done, kill-planner rehearsed end to end (rounds [1, 2, 2, 0]) |
| red-wave page (`uv run python web/server.py`, http://localhost:8765) | v1 works: counters 6 / 25 / 19 frozen at flag time, red wave, green twins, click a red node -> receipt path |
| page test (`tests/test_web.py`) | done |
| README body, LICENSE, disclosure, deploy, MCP beat, video, blog, submission | not started |

## Who does what

| person | role | owns | hours | first task |
|---|---|---|---|---|
| **Aashna** | graph + harness + deploy | spikes S13-S16 (DAY1-SPIKES.md), MCP beat (agent writes its own Cypher; read-only credential), VM + Docker compose + Caddy deploy, review of every query change against `fixture.yaml` numbers | ~13 | run the four README commands on her own laptop from a fresh clone, then S13/S15 |
| **Parth** | page + video + integration | page polish (labels, fonts, projector-readable sizes, a "reset" for retakes), the 3-minute video (script in PLAN.md section 6, three takes, cut, captions), final integration checks D1/D2/D3, vibecoding the page with Claude | ~14 | polish the page against the video script beats; record take 1 rough on Fri |
| **Aman** | paper, legal, submission | README body (pitch, schema diagram, three numbers, limits, "why not Graphiti"), LICENSE (MIT), AI-use disclosure, rules-compliance checklist (new work built in window, FalkorDB primary and central, team locks on submit, "source-available SSPL" wording, no secrets in git), blog post (AirPods side prize), the submission form and confirmation screenshot, and the final read of README as a stranger | ~12 | read `README.md` + PLAN.md sections 1, 7, 9; draft README body and disclosure |

Cross-review rule: whoever wrote a query never signs it off alone. Aashna reviews Parth's page server; Parth reads Aman's README by running every command in it; Aman reads the video script against the rules.

## Checkpoints (EDT)

- **D1 Thu 20:00**: `session1` -> `flag doc_7` -> page shows six red, numbers match the test. (Already true on Parth's laptop; D1 is Aashna and Aman reproducing it.)
- **D2 Fri 20:00**: full run on the VM, video take 1, cut-list decisions. Feature freeze Fri 21:30.
- **D3 Sat 19:00**: submittable: repo public-ready, README numbers = test numbers, video <= 3:00 unlisted, form dry run.
- **Sun 10:30-11:30**: submit. Sun 12:00-14:29: hold, fix only a broken link or a dead VM.
