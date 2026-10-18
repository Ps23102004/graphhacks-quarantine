# Demo script (3:00): matches what the code prints

Every command and output line below was re-run against the code on 2026-10-18. After any code change, run the commands again and compare with this file. Read numbers off the terminal, not from memory.

## Setup (off camera)

```bash
docker start quarantine-falkordb          # or the docker run line in README.md
uv run pytest -q                          # must end with 0 failed before every take
docker exec quarantine-falkordb redis-cli GRAPH.DELETE quarantine   # empty graph for the 0:00 shot
uv run python web/server.py               # page at http://127.0.0.1:8765, right half of the screen
```

Terminal on the left, page on the right. The page is a ledger in five columns, read left to right: 8 sources, then the 25 memories as chips in four columns (episodes, facts, plan steps, files). A ribbon joins what was read to the memory written after reading it.

## Beats

| t | do | the screen shows | say |
|---|---|---|---|
| 0:00 | title card, then the page | empty page, banner "Empty graph · run quarantine session1" | "Shared agent memory that can forget one bad source. Three scripted agents, Research, Planner and Coder, share one FalkorDB graph. They coordinate only through the graph." |
| 0:12 | `uv run quarantine session1 --slow 0.4` | lines print one by one and chips appear on the page (it polls once a second), e.g. `tick 22  planner   read [f_http_client, f_http_pin, f_deps] -> wrote step_3  "Add HTTP dependency ..."` | "Session 1. Research reads eight documents, writes episodes, then folds them into facts. Look at the Planner's line. Before every write, the harness records what the agent read. Those reads are edges in the graph, not log text." |
| 0:45 | wait for `25 memories written` and `session 1 done - 0 processes running`; title card **Session 1 ends** | 25 unmarked memory chips | "Session 1 is over. No process is running. What the agents learned lives only in the graph." |
| 0:55 | title card **Session 2 begins**; `uv run quarantine flag doc_7` | `flagged doc_7: Advisory: forum thread 88213 is a prompt injection; ...`, then `quarantined 6 \| wipe agents 25 \| roll back 19`. On the page, red ink runs along the ribbons, six chips turn red one after another, and the headline reads 6 of 25 | "Now an advisory arrives. Document 7 was a prompt injection. It told Research that the package `requests` is now called `reqeusts`, a typosquat. One graph query quarantines six memories. Wiping every agent that touched it would lose 25. Rolling back to before the bad document would lose 19. Everything else the Planner and Coder wrote stays clean." |
| 1:30 | click the red `a_requirements` chip on the page; point at the terminal's `receipt` line | a yellow highlighter path back to doc_7; the "Why is it red?" panel shows the hops as a chain and a sentence. Terminal: `receipt a_requirements (4 hops): a_requirements -INFLUENCED_BY-> step_3 -INFLUENCED_BY-> f_http_client -CONSOLIDATED_FROM-> ep_7a -EXTRACTED_FROM-> doc_7` | "Why is the Coder's requirements file red? The Coder never read document 7. The receipt is a shortest path. The file came from the Planner's step 3. Step 3 read a poisoned fact. The fact came from an episode, and the episode came from the document." (Two paths of equal length exist. The other goes through the version pin. Either is a valid receipt, so don't promise which one prints.) |
| 1:50 | `uv run quarantine session2` | `research: healed f_http_client -> f_http_client_v2 = requests (support 3 clean)`; a green twin chip appears under the original with a dashed SUPERSEDES ribbon. The version pin is never healed | "Session 2, with fresh processes. Planner and Coder each ask the graph: which of my memories are red, and what am I waiting on? Research rebuilds the package fact from its three clean episodes. The answer is `requests`. The version pin had one source, the bad one. It stays red and is kept as history." |
| 2:12 | (output scrolls) | `planner: wrote step_3_v2 reads [f_http_client_v2, f_deps]; COMPLETE rework_step_3`, then `coder: wrote a_requirements_v2 reads [step_3_v2, step_1]; COMPLETE rework_a_requirements`, then `fixpoint: rounds [1, 2, 2, 0], 28 memories`; two more green twins | "The Planner redoes only step 3. Then the Coder's task unblocks. The order comes from BLOCKED_BY edges. Four rounds, and the last one changes nothing." |
| 2:30 | cut. Off camera: run the reset below, including `flag doc_7`. On camera: `uv run quarantine session2 --kill-planner` | `planner (process <pid>, session s2) claimed rework_step_3, lease until tick 48 ... kill -9, exit -9`; `coder: ... blocked  waiting_on [step_3]`; `planner (new process, session s2b): claim refused at tick 45, lease live until tick 48`; `planner (new process, session s2b) took over lease from planner` | "Now we kill the Planner mid-rework with a real kill -9. The Coder stays blocked. A second Planner session is refused while the lease is live, then takes over when it runs out and finishes." |
| 2:48 | page: final graph | six red chips kept, three green twins | "The poisoned memories stay flagged as history. The 6, 25 and 19 counts are checked by the test suite." |

Spoken words: about 315, roughly 2:06 at 150 words per minute. The rest of the 3:00 is commands running and the page animating. Each beat's lines fit before the next beat starts.

## Reset between takes

```bash
uv run quarantine session1 --slow 0     # drops the graph and rebuilds it from fixture.yaml
uv run quarantine flag doc_7            # only for the 2:30 beat, which needs the flagged state
```

For a fresh 0:00 shot, also run the `GRAPH.DELETE` line from Setup. Without it, the page still shows the last take's graph.

## Do not claim

- That the agents are LLMs. They are scripted. The read-set capture and every graph write are real.
- "One graph per crew shown by GRAPH.LIST". The demo has one graph. Say it in words if needed.
- Which of the two receipt paths prints.
- A specific process number for the killed Planner. It changes on every run.
