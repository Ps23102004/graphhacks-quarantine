# Counterfactual evaluation: is the quarantine sound, and how conservative is it?

`docs/EVAL-HELDOUT.md` shows the Cypher matches an independent restatement of the rule. That cannot show the rule is right. This evaluation does: for every unseen random world and every flagged document it **replays the world with that document never ingested** and asks which memories would actually have been different. Code: `quarantine/counterfactual.py`; run it with `uv run python scripts/counterfactual_eval.py --worlds 150` (seeds 7000+, never used to tune anything); asserted in `tests/test_counterfactual.py`.

## Model

Each memory gets a symbolic content: an episode is its text, a fact is the plurality claim of its supporting episodes, a step or artifact is its text plus the contents of what it read. A memory is *truly affected* if its content differs, or it cannot exist, in the replay without the document.

## Result (150 worlds per model, last run on this commit)

| world model | (world, doc) runs | truly affected | quarantined | false negatives | needless flags | invented receipts | clean memories answered as red | page != graph |
|---|---|---|---|---|---|---|---|---|
| declared read sets | 1340 | 3689 | 10496 | **0** | 6807 (65%) | **0** | **0** | **0** |
| cumulative context | 1340 | 4193 | 11850 | **0** | 7657 (65%) | **0** | **0** | **0** |
| deep chains | 1340 | 7085 | 22051 | **0** | 14966 (68%) | **0** | **0** | **0** |

- **False negative** = truly affected but left clean. Poison keeps being used. Zero.
- **Invented receipt** = a path whose hops are not all declared edges, or that does not end at the flagged document. Every receipt of every quarantined memory is checked. Zero.
- **Clean answered as red** = a memory outside the closure for which the tool did not answer "not in the graph". Zero. The page's red set and counters equal the graph closure in every run. Zero.
- **Needless flag** = quarantined but its content would not have changed (a fact the poisoned episode only agreed or dissented with, and everything built on it). Quarantine is *provenance-level*: sound, not minimal.

## What to say, and what not to say

- Say: "Quarantine means touched by, not proven wrong. It never misses a poisoned memory (0 in 4,020 runs). On random crews about two thirds of what it flags would have kept the same value; healing re-derives those from clean sources, and a fact with fewer than two clean episodes cannot heal (478 of 6,204 needless facts)."
- Say: in the demo, 5 of the 6 quarantined memories truly change; `f_http_client` is a conservative flag that heals back to the same value. The second world (support crew, `kb_5`): 7 flagged, 6 truly change (`f_window`).
- Do not say "only the memories that are wrong". Do not quote the 65% as a general figure: it depends on the generator (70% of a fact's support agrees on its majority claim).
- What it does not show: that declared read sets match what a real agent was influenced by, or that symbolic content is real content. Next step, not done: a value-aware closure that spares memories whose content would not change.

## Retracting a false alarm

`uv run quarantine unflag doc_7` clears the advisory and re-derives quarantine from the documents still flagged (tests/test_unflag.py: demo restored byte-for-byte, randomized multi-document cases against the oracle). It refuses once healing has started, because clean replacements would then outlive their cause; reset with `quarantine session1`.
