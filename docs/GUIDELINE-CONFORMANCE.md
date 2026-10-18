# Conformance with the organizers' build guide and the Track 02 bar

Where the rules come from: the WeMakeDevs kickoff email's walkthrough "How to Build an Agent That Reasons Over a Graph", as summarized by the team on 2026-10-16. The email was not re-read for this document (the mail connector was unavailable), so the six rules below are the team's paraphrase. Each rule has a test in `tests/test_guideline.py`, and each Track 02 criterion has a test in `tests/test_track02_bar.py`. Run both:

```bash
uv run pytest -q tests/test_guideline.py tests/test_track02_bar.py     # 12 passed on commit b31ba1e, 2026-10-18
```

## How this was checked (skeptic review, 2026-10-16)

After the first version of these tests passed, twelve read-only skeptics tried to break the claims, one per rule and one per Track 02 criterion. They were Claude Opus 5.5 sub-agents told to assume each claim was false until shown otherwise, and they probed the real code against throwaway graphs. As recorded at the time, ten of the twelve broke their claim, mostly because the test was weaker than the claim. The skeptic transcripts are not in the repo; the fixes are in commits `d97916e` and `1325dd4`. Every finding was fixed, and the tests were rewritten to the stricter form the skeptics proposed:

- ids with NUL, lone surrogates or 100k characters made the resolvers raise instead of answering "unknown". Fixed: ids are validated before any query.
- `deploy/docker-compose.yml` hard-coded the local host and port, so "local to live" was false for the deployment. Fixed: `${FALKORDB_HOST:-falkordb}` and the other variables, with credentials passed through; checked with `docker compose config`.
- Two MCP tools returned a bare list or a dict with no shape, and the page returned `null` for a clean memory. Fixed: every tool and the page answer in a shape.
- `algo.SPpaths` was called with `maxLen: 50`, so a 63-hop chain silently fell back to `shortestPath`. Fixed: no length limit; the fallback runs only if the procedure raises, and `method` says which one answered.
- `blast_radius` claimed shape "path" with no path. Fixed: one chain per member plus the longest, each as a sentence. `sentence()` silently dropped hops on malformed input. Fixed: it raises.
- The page had a write-path fallback on its read path, and the CLI's agents read through the write path. Fixed: `ro_query` only. A test proves this at runtime by making the write path raise.
- A contested heal recorded only the winner. Fixed: the outvoted clean episodes are linked by their own `OUTVOTED` edge type, which the closure and receipts do not follow, and the rule and runner-up count are stored on the healed fact.
- A memory's receipt vanished if its document was later un-flagged. Fixed: the advisory is recorded on the memory.
- "Procedural memory" was only plan steps. Fixed: the recovery procedure is a `Procedure` node with its rules stored as data, and every incident's tasks `FOLLOWS` it. The harness reads the lease length from it, and the second world follows the same node.

The two skeptics that did not break their claim (rule 5 at the time, and tenant isolation) still found coverage gaps, and those were added: deep-chain SPpaths and a tenant-only node. One thing was not changed: tenant isolation is by graph name on one instance, not by credential. The docs say so.

## The six rules

| # | rule (paraphrased) | how Quarantine meets it | evidence | test |
|---|---|---|---|---|
| 1 | Never let the agent write Cypher. Use a fixed catalog of tools with human-written queries; check every argument against the graph before running anything; an unresolved name returns "unknown" and nothing runs. | `quarantine/answers.py` is the catalog (`why_quarantined`, `why_connected`, `recall`, `blast_radius`). Every query is a string in `answers.py` or `queries.py`. Each tool resolves its ids first (`resolve_memory`, `resolve_doc`, `resolve_node`) and returns shape `unknown` without running the main query. The MCP server exposes these four tools (`trace_provenance_receipt` wraps `why_quarantined`) plus two status tools (`inspect_quarantined_memories`, `get_recovery_status`). No tool takes Cypher. | the test replaces the read path and asserts that, on an unresolved id, the only queries that ran were the resolvers | `test_rule1_agent_never_writes_cypher_fixed_catalog_with_validation` |
| 2 | Reads go through `ro_query`; one graph per tenant via `select_graph`. | `answers.py` reads through `loader.rq`, which calls `ro_query` with no write fallback. `web/server.py`, `mcp_server.py` and `agent_runtime.py` call `g.ro_query` directly. `connect(name)` selects one graph per crew or tenant. | `ro_query` rejects a `CREATE` (observed error: read-only); two crews in two graphs, and an advisory in one leaves the other at 0 quarantined | `test_rule2_reads_use_ro_query_and_one_graph_per_tenant` |
| 3 | Local to live by changing a host and a port (FalkorDB Cloud is the same database). | `loader.connection_kwargs()` reads `FALKORDB_HOST` and `FALKORDB_PORT`, and for Cloud `FALKORDB_USERNAME`, `FALKORDB_PASSWORD` and `FALKORDB_TLS=1`. No other file in `quarantine/` or `web/` constructs a FalkorDB client or names its port. | kwargs asserted for local and for a Cloud-shaped environment; the test scans `quarantine/*.py` and `web/*.py` for `6379`, `FalkorDB(` and `FALKORDB_HOST`; the compose file uses the same variables | `test_rule3_local_to_live_is_environment_only` |
| 4 | Every answer comes in one of four shapes: path (hops shown), memory (with when it was learned), "not in the graph" (deliberately not "nothing is wrong"), "unknown entity". | `answers.shape_path`, `shape_memory`, `shape_not_in_graph`, `shape_unknown`. Every catalog function returns one of them on good and bad input. The MCP tools and the page receipt pass the shape through. | all four produced from the demo graph: `a_requirements` (path), `f_http_client` (memory, learned at tick 11 in session s1 by research), `a_fetch_py` (not_in_graph), `a_fetch_pyy` (unknown) | `test_rule4_every_answer_is_one_of_four_shapes` |
| 5 | Graph algorithms are free tools; `CALL algo.SPpaths` earns its place fastest. | `answers.why_connected` runs `algo.SPpaths` (no length limit, unweighted) over the three provenance edge types and reports `method`. `shortestPath` runs only if the procedure raises, and is labelled. | `method == "algo.SPpaths"` on the pinned image, for the 4-hop receipt and for a 63-hop chain; direction is respected; same length as the Cypher receipt | `test_rule5_graph_algorithm_is_a_tool_and_actually_runs` |
| 6 | Build for "and then": "A led to B which caused C" is a traversal wearing a sentence. | The closure (`FLAG_AND_CLOSE` when `quarantine flag` runs; `TAINT_CLOSURE` in `reconcile`), the read-only `blast_radius`, and `answers.sentence()`, which renders any path as "A was written after reading B, which was consolidated from C, which was extracted from D." The CLI prints it under every receipt ("in words:"). | exact sentence asserted; blast radius of doc_7 = the 6 demo memories; a document nothing derives from is `not_in_graph` | `test_rule6_blast_radius_is_a_traversal_wearing_a_sentence` |

### What changed because of the guide

- We dropped the earlier pitch line "agents author ad-hoc Cypher through the FalkorDB MCP server". The guide says the opposite, and the MCP server now exposes a fixed catalog only.
- `trace_provenance_receipt` used to answer "no path" for both a clean memory and a nonexistent id. Those are now two shapes (`not_in_graph` and `unknown`).
- `algo.SPpaths` was defined in `queries.py` but never called. It now answers "why are these connected".
- FalkorDB Cloud credentials could not be passed (host and port only). Now they come from the environment.

## The Track 02 bar

| criterion (event brief) | test | what it proves | honest limit |
|---|---|---|---|
| memory persists and **updates** across sessions | `test_memory_persists_and_updates_across_separate_processes` | Session 1 and Session 2 are separate OS processes. Session 2 adds 3 memories; the old ones stay, flagged and linked by SUPERSEDES. Both Session nodes own memories (25 and 3). | agents are scripted; the writes are real |
| episodic, semantic, procedural memory | `test_three_memory_kinds_each_with_provenance` | Episode, Fact and PlanStep nodes, each with provenance. The recovery procedure is a `Procedure` node (steps, lease and heal rule stored as data) that every incident's tasks `FOLLOWS`. A second, different crew follows the same node. | the harness writes the procedure; nothing learns it. The heal threshold is still a constant in the Cypher; only the lease is read from the node |
| shared state and handoffs | `test_handoff_is_a_graph_read_not_a_message` | a second process resumes from STARTUP and CLAIM alone; a live lease refuses, an expired lease transfers | |
| high-concurrency reads and writes | `test_concurrent_claims_exactly_one_winner_and_concurrent_writes_all_land` | 16 threads race for one task and exactly one wins (FalkorDB serialises writes per graph; a skeptic showed a check-then-act claim loses this race). 16 concurrent writers all land with full provenance, while a reader polls and never sees a fact without its episode. Audits stay clean. | thread-level, on one machine; not a load test |
| separate memory per tenant | `test_separate_memory_per_tenant_same_question_different_answer` (and rule 2) | same question, two graphs, each tenant gets its own answer | one FalkorDB instance has no per-graph access control: isolation is by graph name, not by credential |
| traceability: the graph does real work | `test_every_decision_is_explainable_by_a_graph_path` | every quarantined memory has a receipt, even after its document is un-flagged. A contested heal records the winner, the outvoted clean episodes (an `OUTVOTED` edge that the closure and receipts do not follow) and the rule. An ungrounded rework still has SUPERSEDES and REWORKED_FOR provenance. | code applies the plurality rule; the graph records the rule's name and parameters, not the code |

## Not covered by any test here

- "Persistent conversation history" in the chat sense. The crew has no chat; its history is the Session and RAN_IN structure.
- Live FalkorDB Cloud. Only the connection kwargs are tested; no Cloud account was used.
- Real agents. The guide's rules are about what an agent may do. Our agents are scripted, so the rules are enforced at the tool layer (MCP) that a real agent would call.
