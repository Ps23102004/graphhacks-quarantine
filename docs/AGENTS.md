# What the agents actually do

## Short answer

The built-in demo uses **scripted worker roles**, not autonomous large language models. A Python coordinator runs the Research, Planner and Coder actions. FalkorDB stores their memories, provenance, repair tasks and claims. The database state decides what can proceed. The text the agents write comes from fixture recipes.

A Model Context Protocol (MCP) server lets an **external AI host** inspect the graph. That host can choose an inspection tool and reason about what it returns. It does not turn the built-in replay into an autonomous coding crew, and the read-only tools cannot change the graph.

An older helper, `AgentDecisionEngine` in `quarantine/agent_runtime.py`, is not used by the CLI or the MCP server. Its tests (`tests/test_agent_runtime.py`) check that separate copy of the rules, so they do not prove anything about live agent behaviour. The CLI and MCP server explain state with `recovery_status`, which reads the same graph the coordinator uses.

## The task they work on

The demo task is a small weather command-line app: fetch current weather, cache results, and declare its Python dependencies. The source documents are **fixture records with descriptive URIs**. Nothing is fetched from the internet during the run. Artifact nodes hold illustrative file text. The demo does not install packages or run the generated weather app.

The poisoned forum record (`doc_7`) claims that `requests` was renamed to `reqeusts` and gives a version pin. That text is wrong on purpose. The fixture models an earlier bad consolidation and what followed from it. It does not show an LLM being fooled live.

| Role | Stored output | What decides its action | What is scripted |
|---|---|---|---|
| Research | Episodes and consolidated Facts | During repair, graph queries count the eligible unquarantined evidence and check the winning claim | Initial episode text and initial fact values |
| Planner | PlanStep memories | Repair-task blockers, available clean replacements and claim ownership | The weather-demo plan and its repair recipes |
| Coder | Artifact memories | Planner dependencies, a valid claim, and the write guard that rejects missing or quarantined inputs | Artifact text, including the demo requirements file |
| Coordinator | Task, claim and session transitions | Readiness, lease state, accepted writes, accepted completion and termination checks | Scheduling policy, not a hidden model prompt |
| External AI host | A readable explanation of tool results | Its model chooses inspection tools and reasons over the returned graph state | Separate integration; the replay needs no model provider or API key |

## Walkthrough

1. **Session 1 stores a trace.** The fixture declares each write's inputs, and the harness creates real provenance edges in FalkorDB. These are declared per-write read sets. They are not influences discovered automatically from an LLM's whole context window.
2. **An advisory flags a source.** A human or an upstream system supplies the document id. Quarantine does not detect prompt injection.
3. **The graph finds downstream memories.** Provenance edges point from newer work to its inputs. The quarantine traversal follows them backwards from the source. Unrelated work stays usable.
4. **Research repairs the facts it can.** The rule is a strict plurality with at least two agreeing eligible episodes. A tie or too little support is left unhealed rather than guessed. This is a voting rule. It does not prove that a claim is true or that the sources are independent.
5. **Planner and Coder repair in dependency order.** A clean replacement is a new node linked to the kept old node by `SUPERSEDES`. Workers must cite the clean replacement, never the quarantined original.
6. **Claims protect ownership.** A worker must hold a valid claim on the task before it publishes a replacement. A worker whose lease expired or whose session was replaced cannot write or report completion (`tests/test_recovery_audit.py`, `test_zombie_complete_cannot_close_a_task_and_rework_is_idempotent`).
7. **Work without a recipe stays visible.** Graph traversal reaches more cases than the weather-demo recipes cover. For a memory with no scripted recipe, `session2` derives the replacement's reads from the graph and stores a placeholder marked `needs_regeneration`. It does not pretend the work is finished.

The demo quarantines six memory nodes. The per-agent and time-based baselines would throw away twenty-five and nineteen. Those are memory counts in this fixture. They are not measurements of tokens, time or money saved.

## What the crash test proves

The `--kill-planner` beat starts a real child process that claims a task and waits, then kills it. It proves that the process really dies and that the claim state survives in the graph. It does not by itself prove safe recovery after every possible write or tool side effect. Separate tests cover torn writes, stale writers and restarts (`tests/test_attack_regressions.py`, `tests/test_recovery_audit.py`). See [validation](VALIDATION.md) for the checks that were run.

## What this prototype does not do

- An autonomous researcher that browses arbitrary sources and decides which claims to trust.
- Automatic injection detection, causal attribution from hidden context, or a universal truth oracle.
- Safe execution or rollback of arbitrary external tools, payments, deployments or installed code.
- A benchmark of high-concurrency throughput, or of savings against another memory product.
- Tenant isolation by authentication. Separate graph names keep the demo data apart; they do not limit what a database administrator can see.

## Why this still fits Graph Hacks

Track 02 is about memory that persists, updates and supports handoffs. Here those transitions and their explanations live in FalkorDB, not in a decorative graph next to some other state store. A recorded session with a real AI host using the MCP tools would add evidence that the memory layer can serve an AI client; that session is not done yet (see [validation](VALIDATION.md)). Neither a deterministic replay nor an MCP handshake decides how judges will rate the entry.

SQL with recursive queries, or graph traversal in application code, could implement the same rules. We use FalkorDB for one property-graph model, native path queries, and coordination state that persists in the same engine. Other tools are not incapable of this.
