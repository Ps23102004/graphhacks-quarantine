# Counterfactual evaluation: what the quarantine misses and what it over-flags

`docs/EVAL-HELDOUT.md` shows the Cypher matches an independent restatement of the rule. That cannot show the rule is useful. This evaluation asks a different question. For each random world and each document in it, replay the world as if that document had never been ingested, and see which memories would really have been different.

- Code: `quarantine/counterfactual.py`.
- Run: `uv run python scripts/counterfactual_eval.py --worlds 150` (seeds 7000 and up; these seeds were not used to tune anything).
- Test: `tests/test_counterfactual.py` (seeds 7000 to 7011 for the three gated models, 7000 to 7005 for the unrecorded-influence model).

## Model

Each memory gets a symbolic content:

- an episode is its text;
- a fact is its stored value; in the replay, if part of its support is gone, it is the plurality claim of the support that remains;
- a step or artifact is its text plus the contents of what it read.

A memory is *truly affected* if its content would differ, or it could not exist, in the replay without the document.

## Result

The table is the 150-world run (`uv run python scripts/counterfactual_eval.py --worlds 150`), first made on 2026-10-17 and repeated on the final code on 2026-10-18 with identical numbers (the seeds are fixed). Output: `docs/RUNS.md`.

| world model | truly affected | quarantined | poisoned memory left clean | quarantined but unchanged | invented receipts | clean memory answered as red | page differs from graph |
|---|---|---|---|---|---|---|---|
| declared read sets | 3,895 | 10,496 | **0** | 6,601 (63%) | **0** | **0** | **0** |
| cumulative context | 4,458 | 11,850 | **0** | 7,392 (62%) | **0** | **0** | **0** |
| deep chains | 7,646 | 22,051 | **0** | 14,405 (65%) | **0** | **0** | **0** |
| **unrecorded influence** (graph gets the declared reads; truth is each agent's whole context) | 4,458 | 10,496 | **329 memories in 169 runs (7% of truly affected)** | 6,367 (61%) | **0** | **0** | **0** |

The script uses other column names: "false negatives" is poisoned memory left clean, and "needless flags" is quarantined but unchanged.

How to read each column:

- **Poisoned memory left clean.** On the first three rows this is 0 *by construction*. The replay follows the same declared read sets as the closure. So these rows show that the traversal and the page implement the rule. They do not show that the read sets are complete. The fourth row measures that. When an agent was influenced by something it never recorded as a read, the closure misses it: 7% of truly affected memories in these random worlds. **The guarantee is only as strong as the recorded read sets.**
- **Invented receipts.** A receipt is invented if a hop is not a recorded edge, or if it does not end at the flagged document. The script checks the receipt of every quarantined memory. Result: 0.
- **Clean memory answered as red.** For every memory outside the closure, the receipt tool must answer "not in the graph". Result: 0.
- **Page differs from graph.** The page's red set, its counter and the `blast_radius` tool must all equal the graph's closure. Result: 0 mismatches.
- **Quarantined but unchanged.** The closure is provenance-level ("touched by"). A fact that the poisoned episode only agreed or disagreed with is quarantined, and so is everything built on it, even though its value would not change. On these random worlds that is about 63%. The generator makes each supporting episode agree with the fact's stored value at least 70% of the time, so one episode rarely changes the majority. Do not quote 63% as a general figure. In the 150-world run, 457 of the facts flagged without need could not heal (clean support below 2).

## The two hand-built worlds

- Demo (`doc_7`): all **6** quarantined memories truly change (`tests/test_counterfactual.py`). `f_http_client` stored the typosquat `reqeusts`; it heals to `requests`.
- Support crew (`kb_5` in `fixtures/support-crew.yaml`): all **7** quarantined memories truly change. We checked this by calling `oracle_tainted` and `truly_affected` on the fixture. No test asserts it.

## What to say, and what not to say

- Say: "Quarantined means touched by a flagged source through a recorded read. On random crews it never missed a memory that the recorded reads connect to the source (0 in 4,020 runs, across the three models where the graph sees every influence), and about two thirds of what it flags would have kept the same value."
- Say: "If an agent was influenced by something it did not record, we miss it. In our random crews that was 7% of the truly affected memories. Recording reads at the source is the next thing to build."
- Do not say "only the memories that are wrong", "exactly" or "precise" without the sentence above next to it.
- What this does not show: that a real agent's influence looks like these generators, or that symbolic content behaves like real content.

## Retracting a false alarm

`uv run quarantine unflag doc_7` clears the advisory and re-derives quarantine from the documents still flagged. `tests/test_unflag.py` checks that the demo graph comes back node for node, and checks randomized multi-document cases against the oracle. `unflag` refuses once healing has started, because clean replacements would then outlive their cause. To start over, run `quarantine session1`.
