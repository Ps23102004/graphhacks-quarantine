# Demo script (3:00) — matches what the code actually prints

Every command and line below was captured from the real CLI on 2026-10-15. Re-capture after any code change: run the commands in section "Reset" and diff against this file. Say numbers from the terminal, never from memory.

## Setup (off camera)

```bash
docker start quarantine-falkordb          # or the docker run line in README.md
uv run python web/server.py               # page at http://localhost:8765, on the right half of the screen
uv run pytest -q                          # must say 18 passed before every take
```

Terminal on the left, page on the right. The page also draws the 8 source documents as a top row of squares (25 memories in four rows below them).

## Beats

| t | do | the screen shows | say |
|---|---|---|---|
| 0:00 | title card, then the page with the empty graph | empty page, banner "empty graph - run quarantine session1" | "Shared agent memory that heals itself. Three agents, Research, Planner and Coder, share one FalkorDB graph. They never message each other; the graph is the coordination." |
| 0:10 | `uv run quarantine session1 --slow 0.4` | lines appear one by one and the nodes appear on the page as each is written, e.g. `tick 22  planner   read [f_http_client, f_http_pin, f_deps] -> wrote step_3  "Add HTTP dependency ..."` | "Session 1. Research reads eight documents and writes episodes, then consolidates them into facts. Watch the Planner's line: before every write, the harness records what the agent read. Those are edges in the graph, not log text." |
| 0:45 | wait for `25 memories written` and `session 1 done - 0 processes running`; title card **Session 1 ends** | all 25 memories grey | "Every process has exited. Nothing is in memory anywhere except the graph." |
| 0:55 | title card **Session 2 begins**; `uv run quarantine flag doc_7` | `flagged doc_7: Advisory: forum thread 88213 is a prompt injection; ...`; then `precise 6 \| per-agent 25 \| time-based 19`; page: six nodes turn red one after another, counters 6 / 25 / 19 | "Next day an advisory lands: document 7 was a prompt injection that told Research the package `requests` is now `reqeusts`, a typosquat. One traversal quarantines six memories. Resetting every compromised agent would wipe 25; forgetting everything after the bad document would wipe 19. The Planner's and Coder's earlier clean work stays green." |
| 1:30 | click the red `requirements.txt` node (`a_requirements`) on the page; point at the terminal's `receipt` line | orange path on the page; footer shows the hops. Terminal: `receipt a_requirements (4 hops): a_requirements -INFLUENCED_BY-> step_3 -INFLUENCED_BY-> f_http_client -CONSOLIDATED_FROM-> ep_7a -EXTRACTED_FROM-> doc_7` | "Why is the Coder's file red? It never read document 7. The receipt is a shortestPath: the file came from the Planner's step 3, which read a poisoned fact, which came from an episode, which came from the document." (Two equal-length paths exist; the other goes through the version pin. Either is a valid receipt, do not promise which one.) |
| 1:50 | `uv run quarantine session2` | `research: healed f_http_client -> f_http_client_v2 = requests (support 3 clean)`; a green twin appears with a dashed SUPERSEDES edge; the version pin is never healed | "Session 2, fresh processes. Planner and Coder each ask: what of mine is red and what am I waiting on? Research re-consolidates the package fact from its three clean episodes: `requests`. The version pin had one source, the bad one, so it stays red and is kept as history." |
| 2:10 | (output scrolls) | `planner: wrote step_3_v2 reads [f_http_client_v2, f_deps]; COMPLETE rework_step_3`, then `coder: wrote a_requirements_v2 reads [step_3_v2, step_1]; COMPLETE rework_a_requirements`, `fixpoint: rounds [1, 2, 2, 0], 28 memories`; two more green twins | "The Planner redoes only step 3. Only then does the Coder's task unblock, in dependency order, from BLOCKED_BY edges. Four rounds, and the last one changes nothing." |
| 2:30 | reset (below), then `uv run quarantine session2 --kill-planner` | `planner (process 37435, session s2) claimed rework_step_3, lease until tick 48 ... kill -9, exit -9`; `coder: ... blocked  waiting_on [step_3]`; `planner (new process, session s2b): claim refused at tick 45, lease live until tick 48`; `planner (new process, session s2b) took over lease from planner` | "Now kill the Planner mid-rework, a real kill -9. The Coder stays blocked, correctly. A new Planner process is refused while the lease is live, takes it over when it expires, and finishes. Nothing was in anyone's memory." |
| 2:50 | page: final graph | six red kept, three green twins | "The poisoned lineage stays flagged as history. FalkorDB 6.0.2, source-available, pinned by digest, and every number you saw is a test assertion." |

## Reset between takes

```bash
uv run quarantine session1 --slow 0     # rebuilds the graph from fixture.yaml
uv run quarantine flag doc_7            # only for the 2:30 beat, which needs the flagged state
```

## Do not claim

- That the agents are LLMs: they are scripted; the read-set capture and every graph write are real.
- "One graph per crew shown by GRAPH.LIST": the demo has one graph; say it in words if needed.
- Which of the two receipt paths prints.
