# Aashna: fresh clone, test and review checklist (Sat night / Sun morning IST)

Goal: prove a stranger can run QUARANTINE from a clean clone, and that nothing on screen is false. Write down every step that differs from "expect". Send the filled checklist to Parth by **Sunday 08:00 EDT (17:30 IST)**. If something fails, stop and send it right away; do not fix code yourself unless Parth asks.

Branch: `improve` at tag `freeze-sat` (Parth will message the exact tag). Tools: Docker Desktop running, `uv`, `git`, Chrome.

## 0. Get the code (5 min)
- [ ] Accept the GitHub collaborator invite (Parth adds your username).
- [ ] `git clone https://github.com/Ps23102004/graphhacks-quarantine.git && cd graphhacks-quarantine && git checkout freeze-sat`

## 1. Follow the README cold (20 min)
Use ONLY the README's Quickstart, word for word, in a new terminal. Do not use anything you remember from before.
- [ ] Step 1 (FalkorDB container) works. If port 6379 is taken: note it.
- [ ] `uv sync --all-extras` works.
- [ ] `uv run pytest -q` -> expect `N passed` (N from the README). Note time and any skips.
- [ ] Demo, two terminals: `uv run python web/server.py`, open http://localhost:8765; then `uv run quarantine session1 --slow 0.4`, `uv run quarantine flag doc_7`, `uv run quarantine session2 --kill-planner`.
  - [ ] flag prints `precise 6 | per-agent 25 | time-based 19` (or the README's current wording)
  - [ ] page: 6 red chips, headline "6 of 25 memories", ledger lists ep_7a, ep_7b, f_http_client, f_http_pin, step_3, a_requirements
  - [ ] click `a_requirements`: yellow highlighter path to doc_7 and a sentence in "Why is it red?"
  - [ ] session2: "kill -9", lease takeover, rounds [1, 2, 2, 0]; page shows green replacement chips under f_http_client, step_3, a_requirements
- [ ] Every command the README shows ran without editing it. List any that needed a change.

## 2. Validation scripts (40 min, can run while you read)
- [ ] `scripts/validate.sh` -> expect `0 failed` (starts its own FalkorDB on :6390)
- [ ] `scripts/validate_compose.sh` -> expect all pass
- [ ] `uv run python scripts/heldout_eval.py --worlds 50 --pipeline-worlds 10` -> expect `0` in the "graph != oracle" and "violations" columns
- [ ] `uv run python scripts/counterfactual_eval.py --worlds 20` -> expect `0` false negatives, `0` invented receipts, `0` wrong 'clean' answers, `0` page != graph
- [ ] Optional if time: `uv run python scripts/mutation_check.py` (about 20 min) -> 0 unexpected survivors

## 3. Try to break it (pick at least five, 30 min)
Use a separate graph name so the demo graph stays clean: add `--graph test` to every command.
- [ ] Flag a document that does not exist: `uv run quarantine flag doc_999 --graph test` -> clear error, nothing red
- [ ] Flag doc_7 then `uv run quarantine unflag doc_7 --graph test` -> "quarantined now: 0", page clean
- [ ] Flag doc_7, run session2, then unflag -> must refuse with "healing has already started"
- [ ] Run `session2` twice -> second run changes nothing
- [ ] Flag two documents (`doc_7` and `doc_3`) -> page banner and counters stay truthful (counters go blank with two advisories)
- [ ] Second world: `uv run quarantine session1 --fixture fixtures/support-crew.yaml --graph sc` then `uv run quarantine flag kb_5 --fixture fixtures/support-crew.yaml --graph sc` -> precise 7 | per-agent 21 | time-based 17
- [ ] MCP tool with junk input: `uv run python scripts/mcp_inspect.py call why_quarantined '{"memory_id": "x\"}) DETACH DELETE (n) //"}'` -> answer shape `unknown`, graph unchanged
- [ ] Page on your phone width (Chrome devtools 375 px): no horizontal page scroll, chart scrolls inside its frame

## 4. Review (60 min, read the diff, not the whole repo)
`git diff freeze-v1..freeze-sat --stat`, then read in this order:
- [ ] `quarantine/loader.py` `unflag` and `quarantine/queries.py` (UNFLAG_DOC, RESET_QUARANTINE, HEAL_STARTED): can it leave a memory clean that a still-flagged document reaches?
- [ ] `quarantine/counterfactual.py`: is "truly affected" computed independently of the Cypher? Any way it could hide a false negative?
- [ ] Any fix commit made tonight (Parth will list them): each has a test that fails without it.
- [ ] README: every number matches what you saw in steps 1 to 3. Mark any sentence you could not verify.

## 5. Send back
- [ ] For each section: PASS, or the exact command plus the output that differed.
- [ ] Your merge decision: `improve` -> `main` yes or no, and why.
