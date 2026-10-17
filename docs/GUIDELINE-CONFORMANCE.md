# Conformance with the organizers' build guide and the Track 02 bar

Source of the rules: the WeMakeDevs kickoff email's walkthrough "How to Build an Agent That Reasons Over a Graph", as distilled by the team on 2026-10-16. The email itself was not re-read for this document (the mail connector was unavailable); the six rules below are the team's paraphrase. Every rule has a test in `tests/test_guideline.py`; every Track 02 criterion has a test in `tests/test_track02_bar.py`. Run both:

```bash
uv run pytest -q tests/test_guideline.py tests/test_track02_bar.py     # expect 12 passed
```

## How this was verified (ultracode pass, 2026-10-16)

After the first version of these tests passed, twelve independent read-only skeptics (one per rule, one per Track 02 criterion; Claude Opus 5.5 sub-agents with a "default to refuted" brief) tried to break each claim by probing the real code against throwaway graphs. Ten of twelve were refuted, mostly because the tests were weaker than the claims. Everything they found was fixed and the tests were rewritten to the stricter form they proposed:

- ids with NUL, lone surrogates or 100k characters made the resolvers raise instead of answering "unknown" (fixed: validated before any query);
- `deploy/docker-compose.yml` hard-coded the local host and port, so "local to live" was false for the deployment (fixed: `${FALKORDB_HOST:-falkordb}` etc., credentials passed through, verified with `docker compose config`);
- two MCP tools returned a bare list / a dict with no shape, and the page returned `null` for a clean memory (fixed: every tool and the page answer in a shape);
- `algo.SPpaths` was called with `maxLen: 50`, so a 63-hop chain silently fell back to `shortestPath` (fixed: unbounded; the fallback runs only if the procedure raises, and `method` says which answered);
- `blast_radius` claimed shape "path" with no path (fixed: one chain per member plus the longest, each as a sentence); `sentence()` silently dropped hops on malformed input (fixed: raises);
- the read path had a write-path fallback in the page and the CLI's agents read through the write path (fixed: `ro_query` only, proven at runtime with the write path monkeypatched to raise);
- a contested heal recorded only the winner (fixed: outvoted clean episodes are linked with their own `OUTVOTED` edge type, which the closure and receipts do not follow, and the rule and runner-up count are stored on the healed fact);
- a memory's receipt vanished if its document was later un-flagged (fixed: the advisory is recorded on the memory);
- "procedural memory" was only plan steps (fixed: the recovery procedure is a `Procedure` node every incident's tasks `FOLLOWS`, authored, with its rules as data; the harness reads the lease length from it; the second world follows the same node).

Two skeptics did not refute (rule 5 at the time, and tenant isolation); their coverage gaps were added anyway (deep-chain SPpaths, a tenant-only node). The one thing not changed: tenant isolation is by graph name on one instance, not by credential; the docs say so.

## The six rules

| # | rule (paraphrased) | how Quarantine meets it | evidence | test |
|---|---|---|---|---|
| 1 | Never let the agent write Cypher. Fixed catalog of tools with human-written queries; check every argument against the graph before running anything; an unresolved name returns "unknown" and nothing runs. | `quarantine/answers.py` is the catalog (`why_quarantined`, `why_connected`, `recall`, `blast_radius`); every query is a string in `answers.py` or `queries.py`; each tool resolves its ids first (`resolve_memory`, `resolve_doc`) and returns shape `unknown` without running the main query. The MCP server exposes only these tools plus two status tools; no tool takes Cypher. | the test monkeypatches the read path and asserts that on an unresolved id the only queries that ran were the resolvers | `test_rule1_agent_never_writes_cypher_fixed_catalog_with_validation` |
| 2 | Reads go through `ro_query`; one graph per tenant via `select_graph`. | `loader.rq` uses `ro_query`; `answers.py`, `web/server.py`, `mcp_server.py`, `agent_runtime.py` read only through it. `connect(name)` selects one graph per crew/tenant. | `ro_query` rejects a `CREATE` (observed error: read-only); two crews in two graphs, an advisory in one leaves the other at 0 quarantined | `test_rule2_reads_use_ro_query_and_one_graph_per_tenant` |
| 3 | Local to live by changing a host and a port (FalkorDB Cloud is the same database). | `loader.connection_kwargs()` reads `FALKORDB_HOST`, `FALKORDB_PORT`, and for Cloud `FALKORDB_USERNAME`, `FALKORDB_PASSWORD`, `FALKORDB_TLS=1`. No other file constructs a client or names a port. | kwargs asserted for local and for a Cloud-shaped environment; grep over `quarantine/` for hard-coded hosts | `test_rule3_local_to_live_is_environment_only` |
| 4 | Every answer in one of four shapes: path (hops shown), memory (with when it was learned), "not in the graph" (deliberately not "nothing is wrong"), "unknown entity". | `answers.shape_path / shape_memory / shape_not_in_graph / shape_unknown`; every catalog function returns one of them on good and bad input; the MCP tools and the page receipt pass the shape through. | all four produced from the demo graph: `a_requirements` (path), `f_http_client` (memory, learned tick 11, session s1, by research), `a_fetch_py` (not_in_graph), `a_fetch_pyy` (unknown) | `test_rule4_every_answer_is_one_of_four_shapes` |
| 5 | Graph algorithms are free tools; `CALL algo.SPpaths` earns its place fastest. | `answers.why_connected` runs `algo.SPpaths` (unbounded, unweighted) over the three provenance edge types and reports `method`; `shortestPath` runs only if the procedure raises, and is labelled. | `method == "algo.SPpaths"` on the pinned image for the 4-hop receipt and for a 63-hop chain; direction respected; same length as the Cypher receipt | `test_rule5_graph_algorithm_is_a_tool_and_actually_runs` |
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
| episodic, semantic, procedural memory | `test_three_memory_kinds_each_with_provenance` | Episode/Fact/PlanStep nodes with provenance; the recovery procedure is a `Procedure` node (steps, lease, heal rule as data) that every incident's tasks `FOLLOWS`; a second, different crew follows the same node | the procedure is written by the harness, not learned; the heal threshold is still a constant in the Cypher, only the lease is read from the node |
| shared state and handoffs | `test_handoff_is_a_graph_read_not_a_message` | a second process resumes from STARTUP + CLAIM alone; live lease refuses, expired lease transfers | |
| high-concurrency reads and writes | `test_concurrent_claims_exactly_one_winner_and_concurrent_writes_all_land` | 16 threads race one task: exactly one winner (FalkorDB serialises writes per graph; a skeptic's check-then-act claim lost the same race 8 of 10 runs); 16 concurrent writers all land with full provenance while a reader polls and never sees a torn pair; audits clean | thread-level, on one machine; not a load test |
| separate memory per tenant | `test_separate_memory_per_tenant_same_question_different_answer` (and rule 2) | same question, two graphs, each tenant's own answer | one FalkorDB instance has no per-graph ACL: isolation is by graph name, not by credential |
| traceability / the graph does real work | `test_every_decision_is_explainable_by_a_graph_path` | every quarantined memory has a receipt (even after its document is un-flagged); a contested heal records winner, dissent (`rejected: true`) and the rule; an ungrounded rework still has SUPERSEDES and REWORKED_FOR provenance | the plurality rule is applied by code; the graph records the rule's name and parameters, not the code |

## Not covered by any test here

- "Persistent conversation history" in the chat sense: the crew has no chat; its history is the Session/RAN_IN structure.
- Live FalkorDB Cloud: only the connection kwargs are tested; no Cloud account was used.
- Real agents: the guide's rules are about what an agent may do; our agents are scripted, so the rules are enforced at the tool layer (MCP) that a real agent would call.
