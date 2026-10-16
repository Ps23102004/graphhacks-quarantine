# What the agents actually do

## Short answer

The built-in demo uses **scripted worker roles**, not autonomous large language models. A Python coordinator runs Research, Planner and Coder actions. FalkorDB stores their memories, provenance, repair tasks and claims. Database state determines what can proceed; the demo's generated text comes from fixture recipes.

A Model Context Protocol (MCP) server lets an **external AI host** inspect this graph. That host can reason about tool results and choose an inspection tool. It does not turn the built-in replay into an autonomous coding crew, and the read-only tools do not grant permission to change the graph.

The older `AgentDecisionEngine` helper was disconnected from the CLI. Passing tests of that separate Python rule copy did not prove live agent behavior. The build audit replaces that approach with explanations derived from the same graph state the coordinator uses.

## What task are they working on?

The demonstration task is a small weather command-line application: fetch current weather, cache results and declare its Python dependencies. Source documents are **fixture records with descriptive URIs**, not pages fetched from the internet during the run. Artifact nodes contain illustrative file text; the demo does not install packages or execute the generated weather application.

The poisoned forum record claims that `requests` was renamed to `reqeusts` and supplies a version pin. That text is deliberately wrong. The fixture models a prior bad consolidation and its consequences. It does not demonstrate an LLM being fooled live.

| Role | Stored output | What determines its action? | What is scripted? |
|---|---|---|---|
| Research | Episodes and consolidated Facts | During repair, graph queries count eligible unquarantined evidence and check the winning claim | Initial episode text and initial fact values |
| Planner | PlanStep memories | Repair-task blockers, available clean replacements and claim ownership | The weather-demo plan and supported repair recipes |
| Coder | Artifact memories | Planner dependencies, valid claim and the write guard rejecting missing or quarantined inputs | Artifact text, including the demonstration requirements file |
| Coordinator | Task/claim/session transitions | Readiness, lease state, accepted writes, accepted completion and termination checks | Scheduling policy, not a hidden model prompt |
| External AI host | A human-readable explanation of tool results | Its model chooses inspection tools and reasons over returned graph state | Separate integration; no built-in provider or API key is required for replay |

## Walkthrough

1. **Session 1 stores a trace.** The fixture declares each write's inputs. The harness creates real provenance edges in FalkorDB. These are declared per-write read sets, not automatically discovered influences from an entire LLM context window.
2. **An advisory flags a source.** A human or upstream system supplies the document ID. Quarantine does not automatically detect prompt injection.
3. **The graph finds downstream memories.** Provenance edges point from newer work toward its inputs. The quarantine traversal follows those relationships backward from the source. Unrelated work remains usable.
4. **Research repairs eligible facts.** The policy uses a strict plurality with at least two agreeing eligible episodes. A tie or insufficient support does not justify guessing. This is a voting policy, not proof that a claim is true or that sources are independent.
5. **Planner and Coder repair in dependency order.** A clean replacement is a new node connected to the retained old node by `SUPERSEDES`. Workers must cite the clean replacement, never the quarantined original.
6. **Claims protect work ownership.** A worker must hold the relevant valid claim before publishing a replacement. Expired or superseded workers must not be able to write or report completion.
7. **Unsupported work stays explicit.** General graph traversal is broader than the weather-demo generation recipes. An unsupported repair must be reported as pending, not falsely completed.

The original demonstration quarantines six memory nodes. Per-agent and time-based baselines would invalidate twenty-five and nineteen respectively. Those are fixture-specific memory counts, not measurements of tokens, time or money saved.

## What a crash test proves

The original `--kill-planner` beat kills a real child that claims a task and waits. It proves process death and durable claim state. It does not by itself prove safe recovery after every possible write or tool side effect. The build audit adds separate interrupted-write, stale-writer and restart scenarios. See [validation](VALIDATION.md) for the checks actually run.

## What remains outside this prototype

- An autonomous researcher browsing arbitrary sources and deciding which claims to trust.
- Automatic injection detection, hidden-context causal attribution or a universal truth oracle.
- Safe execution or rollback of arbitrary external tools, payments, deployments or installed code.
- A benchmark proving high-concurrency throughput or savings against another memory product.
- Authentication-based tenant isolation. Separate graph names isolate stored demo data, not the permissions of a database administrator.

## Why this still fits Graph Hacks

Track 02 emphasizes memory that persists, updates and supports handoffs. Here those transitions and their explanations are backed by FalkorDB, not a decorative graph beside another state store. A real AI-host inspection session supplies additional evidence that the memory layer can serve an AI client. Neither a deterministic replay nor an MCP handshake alone guarantees how judges will evaluate the entry.

SQL with recursive queries or application graph traversal could implement equivalent semantics. The reason to use FalkorDB here is a coherent property-graph model, native path queries and persistent coordination state in the same engine, not computational impossibility elsewhere.
