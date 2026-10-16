# Conformance with the organizers' build guide and the Track 02 bar

Source of the rules: the WeMakeDevs kickoff email's walkthrough "How to Build an Agent That Reasons Over a Graph", as distilled by the team on 2026-10-16. The email itself was not re-read for this document (the mail connector was unavailable); the six rules below are the team's paraphrase. Every rule has a test in `tests/test_guideline.py`; every Track 02 criterion has a test in `tests/test_track02_bar.py`. Run both:

```bash
uv run pytest -q tests/test_guideline.py tests/test_track02_bar.py     # expect 12 passed
```

## The six rules

| # | rule (paraphrased) | how Quarantine meets it | evidence | test |
|---|---|---|---|---|
| 1 | Never let the agent write Cypher. Fixed catalog of tools with human-written queries; check every argument against the graph before running anything; an unresolved name returns "unknown" and nothing runs. | `quarantine/answers.py` is the catalog (`why_quarantined`, `why_connected`, `recall`, `blast_radius`); every query is a string in `answers.py` or `queries.py`; each tool resolves its ids first (`resolve_memory`, `resolve_doc`) and returns shape `unknown` without running the main query. The MCP server exposes only these tools plus two status tools; no tool takes Cypher. | the test monkeypatches the read path and asserts that on an unresolved id the only queries that ran were the resolvers | `test_rule1_agent_never_writes_cypher_fixed_catalog_with_validation` |
| 2 | Reads go through `ro_query`; one graph per tenant via `select_graph`. | `loader.rq` uses `ro_query`; `answers.py`, `web/server.py`, `mcp_server.py`, `agent_runtime.py` read only through it. `connect(name)` selects one graph per crew/tenant. | `ro_query` rejects a `CREATE` (observed error: read-only); two crews in two graphs, an advisory in one leaves the other at 0 quarantined | `test_rule2_reads_use_ro_query_and_one_graph_per_tenant` |
| 3 | Local to live by changing a host and a port (FalkorDB Cloud is the same database). | `loader.connection_kwargs()` reads `FALKORDB_HOST`, `FALKORDB_PORT`, and for Cloud `FALKORDB_USERNAME`, `FALKORDB_PASSWORD`, `FALKORDB_TLS=1`. No other file constructs a client or names a port. | kwargs asserted for local and for a Cloud-shaped environment; grep over `quarantine/` for hard-coded hosts | `test_rule3_local_to_live_is_environment_only` |
| 4 | Every answer in one of four shapes: path (hops shown), memory (with when it was learned), "not in the graph" (deliberately not "nothing is wrong"), "unknown entity". | `answers.shape_path / shape_memory / shape_not_in_graph / shape_unknown`; every catalog function returns one of them on good and bad input; the MCP tools and the page receipt pass the shape through. | all four produced from the demo graph: `a_requirements` (path), `f_http_client` (memory, learned tick 11, session s1, by research), `a_fetch_py` (not_in_graph), `a_fetch_pyy` (unknown) | `test_rule4_every_answer_is_one_of_four_shapes` |
| 5 | Graph algorithms are free tools; `CALL algo.SPpaths` earns its place fastest. | `answers.why_connected` runs `algo.SPpaths` over the three provenance edge types and reports `method`; `shortestPath` is only a fallback and is labelled as such. | `method == "algo.SPpaths"` on the pinned image; same length as the Cypher receipt | `test_rule5_graph_algorithm_is_a_tool_and_actually_runs` |
| 6 | Build for "and then": "A led to B which caused C" is a traversal wearing a sentence. | the closure (`TAINT_CLOSURE`), the read-only `blast_radius`, and `answers.sentence()` which renders any path as "A was written after reading B, which was consolidated from C, which was extracted from D." The CLI prints it under every receipt ("in words:"). | exact sentence asserted; blast radius of doc_7 = the 6 demo memories; a document nothing derives from is `not_in_graph` | `test_rule6_blast_radius_is_a_traversal_wearing_a_sentence` |

### What changed because of the guide

- Dropped the earlier pitch line "agents author ad-hoc Cypher through the FalkorDB MCP server". The guide says the opposite, and the MCP server now exposes a fixed catalog only.
- `trace_provenance_receipt` used to answer "no path" for both a clean memory and a nonexistent id. Those are now two shapes (`not_in_graph` vs `unknown`).
- `algo.SPpaths` was defined in `queries.py` but never called. It now answers "why are these connected".
- FalkorDB Cloud credentials were impossible to pass (host/port only). Now environment only.

## The Track 02 bar

| criterion (event brief) | test | what it proves | honest limit |
|---|---|---|---|
| memory persists and **updates** across sessions | `test_memory_persists_and_updates_across_separate_processes` | Session 1 and 2 are separate OS processes; 3 memories are added, old ones stay, flagged and linked by SUPERSEDES; both Session nodes own memories | agents are scripted; the writes are real |
| episodic, semantic, procedural memory | `test_three_memory_kinds_each_with_provenance` | Episode/Fact/PlanStep nodes with provenance; the rework procedure is Task + BLOCKED_BY in the graph | "procedural" here is the plan and the rework procedure for one incident, not a learned skill reused across incidents |
| shared state and handoffs | `test_handoff_is_a_graph_read_not_a_message` | a second process resumes from STARTUP + CLAIM alone; live lease refuses, expired lease transfers | |
| high-concurrency reads and writes | `test_concurrent_claims_exactly_one_winner_and_concurrent_writes_all_land` | 16 threads race one task: exactly one winner (FalkorDB serialises writes per graph); 16 concurrent writers all land with provenance; audits clean | thread-level, on one machine; not a load test |
| separate memory per tenant | `test_separate_memory_per_tenant_same_question_different_answer` (and rule 2) | same question, two graphs, each tenant's own answer | one FalkorDB instance has no per-graph ACL: isolation is by graph name, not by credential |
| traceability / the graph does real work | `test_every_decision_is_explainable_by_a_graph_path` | every quarantined memory has a receipt; a healed fact names its clean support by id | the plurality rule itself is code, not a node; only its outcome is in the graph |

## Not covered by any test here

- "Persistent conversation history" in the chat sense: the crew has no chat; its history is the Session/RAN_IN structure.
- Live FalkorDB Cloud: only the connection kwargs are tested; no Cloud account was used.
- Real agents: the guide's rules are about what an agent may do; our agents are scripted, so the rules are enforced at the tool layer (MCP) that a real agent would call.
