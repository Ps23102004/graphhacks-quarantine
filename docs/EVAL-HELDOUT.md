# Held-out evaluation: does it work on data it never saw?

There is no training in this project (no model is fit), so "unseen data" means: worlds whose numbers nobody tuned. The demo fixture was hand-built, and its 6 / 25 / 19 depend on that hand-built read-set list. This evaluation removes that dependence for the implementation.

## What was run

`uv run python scripts/heldout_eval.py --worlds 300` generates random crews (6 to 12 documents, 3 to 5 agents, 4 to 8 facts with disagreeing sources, 3 to 7 plan steps, 2 to 5 artifacts, random read sets that only point backwards in time), loads each into FalkorDB with the same loader the demo uses, flags **every** document in turn, and compares the graph's answers with `quarantine/worldgen.py`'s oracle, which recomputes everything with plain Python sets (a fixpoint, sharing no code or query text with `queries.py`).

Compared exactly, per case: the quarantined set, both baseline counts, which facts are healable, and what each heals to (claim and supporting-episode count).

Seeds 1000 and up for this report; the test suite uses 2000+ and 3000+. The seeds were never used to adjust a query or rule.

## Results (300 worlds per model, 2645 cases each; last run on this commit)

| world model | cases | graph != oracle | precise quarantine | naive: wipe agents | naive: time-based | clean lost: wipe agents | clean lost: time-based |
|---|---|---|---|---|---|---|---|
| declared read sets (the demo's model) | 2645 | **0** | 29% | 92% | 78% | 91% | 68% |
| cumulative context (pessimistic) | 2645 | **0** | 32% | 92% | 78% | 91% | 67% |
| deep chains | 2645 | **0** | 45% | 92% | 83% | 92% | 67% |

"Precise quarantine" is the mean share of a world's memories that the graph quarantines. The naive columns are the mean share each policy would discard. "Clean lost" is the share of the world's non-poisoned memories that policy throws away.

## A real bug this found

A hop bound in the closure query (`*1..10`) silently left poisoned memories deeper than ten hops marked clean. The random worlds did not hit it (they have short alternative paths), but a hand-built chain world did: with 9 chained steps the graph already missed the last step and the artifact, which would then keep being used. Fixed by removing the bound (the graph is a DAG because reads only point backwards in time), with a regression test on a 40-step chain and mutation checks that fail if any of the closure, per-agent baseline or receipt is bounded again.

## What this does and does not show

- It shows the Cypher implements the stated rules (closure, baselines, strict-plurality heal) on thousands of cases the demo did not contain, including cycles of disagreement among sources and deep chains.
- The oracle encodes the same rules, so it cannot show that the rules are the right ones. It is an independent implementation of the specification, not independent evidence that the specification is good.
- It does not show that captured read sets match what a real agent was influenced by. The "cumulative" row is the pessimistic case (every later write counts everything its author had read or written before); precise quarantine rises only from 29% to 32% in these random worlds, but this depends on the generator.
- The baseline percentages depend on the generator: with only 3 to 5 agents, wiping every compromised agent discards almost everything. Do not quote 92% as a general figure; say "in 300 random crews of 3 to 5 agents".
- The generator is not real agent traffic. A study on logged traces from a real multi-agent run would be the next step and is not done.
