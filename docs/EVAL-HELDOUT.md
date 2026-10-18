# Held-out evaluation: data the code never saw

This project trains nothing (no model is fit), so "unseen data" here means worlds whose numbers nobody tuned. The demo fixture was built by hand, and its 6 / 25 / 19 depend on its hand-written read sets. This evaluation checks the implementation without that dependence.

## What was run

`uv run python scripts/heldout_eval.py --worlds 300` generates random crews with `quarantine/worldgen.py`:

- 6 to 12 documents, each giving 1 or 2 episodes;
- 3 to 5 agents (one researcher plus 2 to 4 workers);
- 4 to 8 facts, whose supporting episodes can disagree;
- 3 to 7 plan steps (12 to 16 in the deep-chain model) and 2 to 5 artifacts;
- random read sets that only point backwards in time.

It loads each world into FalkorDB with the same loader the demo uses. Then it flags **every** document in turn and compares the graph's answers with the oracle in `quarantine/worldgen.py`. The oracle recomputes everything with plain Python sets and shares no code or query text with `queries.py`.

For each case it compares exactly: the quarantined set, both baseline counts, which facts are healable, and what each one heals to (claim and number of supporting episodes).

This report uses seeds 1000 and up. The tests use 2000+ and 3000+. These seeds were not used to adjust a query or rule.

## Results (300 worlds per model, 2,645 cases each)

Re-run on commit `b31ba1e` on 2026-10-18 with the command above; every cell below matches that output.

| world model | cases | graph != oracle | graph quarantine | naive: wipe agents | naive: time-based | clean lost: wipe agents | clean lost: time-based |
|---|---|---|---|---|---|---|---|
| declared read sets (the demo's model) | 2645 | **0** | 29% | 92% | 78% | 91% | 68% |
| cumulative context (pessimistic) | 2645 | **0** | 32% | 92% | 78% | 91% | 67% |
| deep chains | 2645 | **0** | 45% | 92% | 83% | 92% | 67% |

"Graph quarantine" is the mean share of a world's memories that the graph quarantines. The naive columns are the mean share each policy would throw away. "Clean lost" is the share of the world's non-poisoned memories that the policy throws away. All means are over the cases where the flagged document reaches at least one memory.

## Whole Session 2 on unseen worlds

The same script also runs the full repair to a fixpoint: flag, closure, heal, claim with leases, and rework derived from the graph. Derived rework (`loader.derive_rework`) keeps clean reads, swaps quarantined reads for their healed twins, and drops reads that can never heal. Each run must pass these checks:

- the set of twins equals what the oracle predicts (every tainted step and artifact, plus every healable fact);
- every task reaches `done`;
- the three audit queries return 0;
- the quarantined memories left without a replacement are exactly the episodes plus the unhealable facts.

| world model | worlds | (world, doc) runs | invariant violations |
|---|---|---|---|
| declared read sets | 100 | 878 | 0 |
| cumulative context | 100 | 878 | 0 |
| deep chains | 100 | 878 | 0 |

This found two more bugs:

1. A step whose inputs were all poisoned beyond repair had an empty read set. The rework write (an `UNWIND` over nothing) returned no row and raised. Now a twin with no inputs is marked `ungrounded`.
2. The first version of derived rework copied the quarantined memory's text into the clean twin. A security review flagged this as poison laundering. Now a derived twin carries a placeholder marked `needs_regeneration` until an agent supplies real content.

Both have regression tests in `tests/test_heldout.py`.

## A real bug this found

A hop bound in the closure query (`*1..10`) silently left poisoned memories deeper than ten hops marked clean. The random worlds did not hit it, because they have short alternative paths. A hand-built chain world did: with 9 chained steps, the last step and the artifact sit 11 and 12 hops from the document, so the bounded query missed both and they would have stayed in use.

The fix removed the bound. That is safe because the graph is a DAG: reads only point backwards in time. What guards it now:

- `test_closure_has_no_hop_bound` (in `tests/test_heldout.py`) on a 40-step chain;
- `test_rule5_graph_algorithm_is_a_tool_and_actually_runs` checks `FLAG_AND_CLOSE`, the statement `quarantine flag` and this evaluation run, against the oracle on a 60-step chain;
- mutants in `scripts/mutation_check.py` that fail the suite if `FLAG_AND_CLOSE`, `TAINT_CLOSURE` (used by `reconcile`), the per-agent baseline or the receipt is bounded at 10 hops again.

## What this does and does not show

- It shows the Cypher implements the stated rules (closure, baselines, strict-plurality heal) on thousands of cases the demo did not contain, including disagreeing sources and deep chains.
- The oracle encodes the same rules, so it cannot show that the rules are the right ones. It is an independent implementation of the specification. It is not independent evidence that the specification is good. `docs/COUNTERFACTUAL.md` asks that question.
- It does not show that captured read sets match what a real agent was influenced by. The "cumulative" row is the pessimistic case: every later write counts everything its author had read or written before. Graph quarantine rises only from 29% to 32% there, but that depends on the generator.
- The baseline percentages also depend on the generator. With only 3 to 5 agents, wiping every compromised agent throws away almost everything. Do not quote 92% as a general figure; say "in 300 random crews of 3 to 5 agents".
- The generator is not real agent traffic. A study on logged traces from a real multi-agent run would be the next step. It has not been done.
