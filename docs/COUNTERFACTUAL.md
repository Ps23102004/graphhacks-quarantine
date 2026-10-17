# Counterfactual evaluation: how sound is the quarantine, and how conservative?

`docs/EVAL-HELDOUT.md` shows the Cypher matches an independent restatement of the rule. That cannot show the rule is useful. This evaluation asks: for every unseen random world and every flagged document, **replay the world with that document never ingested and see which memories would actually have been different.** Code: `quarantine/counterfactual.py`; run `uv run python scripts/counterfactual_eval.py --worlds 150` (seeds 7000 and up, never used to tune anything); asserted in `tests/test_counterfactual.py`.

## Model

Each memory gets a symbolic content: an episode is its text; a fact is its stored value (and, in the replay, the plurality claim of the support that remains); a step or artifact is its text plus the contents of what it read. A memory is *truly affected* if its content differs, or it cannot exist, in the replay without the document.

## Result (150 worlds per model, 1,340 (world, document) runs per row)

| world model | truly affected | quarantined | poisoned memory left clean | quarantined but unchanged | invented receipts | clean memory answered as red | page differs from graph |
|---|---|---|---|---|---|---|---|
| declared read sets | 3,895 | 10,496 | **0** | 6,601 (63%) | **0** | **0** | **0** |
| cumulative context | 4,458 | 11,850 | **0** | 7,392 (62%) | **0** | **0** | **0** |
| deep chains | 7,646 | 22,051 | **0** | 14,405 (65%) | **0** | **0** | **0** |
| **unrecorded influence** (graph gets the declared reads; truth is each agent's whole context) | 4,458 | 10,496 | **329 memories in 169 runs (7% of truly affected)** | 6,367 (61%) | **0** | **0** | **0** |

How to read it:

- **Poisoned memory left clean.** On the first three rows this is 0 *by construction*: the replay follows the same declared read sets the closure follows, so it shows the traversal and the page implement the rule, not that the read sets are complete. The fourth row is the honest measure of that second question: when an agent was influenced by something it never recorded as a read, the closure misses it (7% of truly affected memories in these random worlds). **The guarantee is exactly as strong as the recorded read sets.**
- **Invented receipt:** a path with a hop that is not a recorded edge, or that does not end at the flagged document. Every receipt of every quarantined memory is checked. 0.
- **Clean memory answered as red:** a memory outside the closure for which the tools did not answer "not in the graph". 0. The page's red set and counters equal the graph's closure in every run. 0.
- **Quarantined but unchanged:** the closure is provenance-level ("touched by"): a fact the poisoned episode only agreed or disagreed with, and everything built on it, is quarantined although its content would not change. About 63% on random worlds, because 70% of a generated fact's support agrees on its majority claim; do not quote 63% as a general figure. 457 of the unnecessarily flagged facts cannot heal (clean support below 2).

## The two hand-built worlds

- Demo (`doc_7`): all **6** quarantined memories truly change. `f_http_client` stored the typosquat `reqeusts`; it heals to `requests`.
- Support crew (`kb_5`): all **7** quarantined memories truly change.

## What to say, and what not to say

- Say: "Quarantined means touched by a flagged source through a recorded read. On random crews it never missed a memory the recorded reads connect to the source (0 in 4,020 runs), and about two thirds of what it flags would have kept the same value."
- Say: "If an agent was influenced by something it did not record, we miss it: in our random crews 7% of the truly affected memories. Recording reads at the source is the thing to build next."
- Do not say "only the memories that are wrong", "exactly", or "precise" without the sentence above next to it.
- What this does not show: that a real agent's influence looks like these generators, or that symbolic content is real content.

## Retracting a false alarm

`uv run quarantine unflag doc_7` clears the advisory and re-derives quarantine from the documents still flagged (`tests/test_unflag.py`: demo restored node for node, randomized multi-document cases against the oracle). It refuses once healing has started, because clean replacements would then outlive their cause; reset with `quarantine session1`.
