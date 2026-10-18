# Forgetting one bad source without wiping the clean work

*Graph Hacks 2026, Track 02 (Agent Memory and Coordination). Team: Parth Singh, Amandeep Kaushik, Aashna Tyagi.*

![The provenance ledger: a receipt path from a quarantined requirements file back to the poisoned document](media/hive-receipt.png)

## The problem

When agents share a memory, one poisoned web page can travel a long way. In our demo, a forum thread tells the research agent that the Python package `requests` is now called `reqeusts`, a typosquat. Research turns that into a fact. The planner reads the fact and writes a plan step. The coder reads the plan and writes `requirements.txt`. The coder never saw the forum thread, but its file is poisoned anyway.

Later an advisory arrives: that thread was a prompt injection. Now someone has to decide what to throw away. The two blunt options are to reset every agent that touched the poison, or to roll memory back to before the bad document arrived. Our demo world has 25 memories. The first option throws away all 25. The second throws away 19. Most of that was clean work.

## What we built

QUARANTINE keeps the crew's memory in FalkorDB. Every memory is a node: an episode extracted from a document, a fact consolidated from episodes, a plan step, a file. Every write also records, as edges, what the agent read before writing it. Finding what the poison reached is then one traversal:

```cypher
MATCH (d:Doc {id: $doc})<-[:EXTRACTED_FROM|CONSOLIDATED_FROM|INFLUENCED_BY*1..]-(m:Memory)
SET m.quarantined = true
```

In the demo that marks 6 of the 25 memories. Click one and the page shows its receipt: the path back to the source, written as a sentence. For the requirements file it reads: the file was written after reading step 3, which was written after reading a poisoned fact, which was consolidated from an episode, which was extracted from the forum thread. (Two paths of equal length exist, one through the package-name fact and one through the version-pin fact. Either is a valid receipt.)

Then the crew repairs its memory. A fact is rebuilt only from clean episodes, and only when at least two of them agree and their claim has more votes than any other claim. The package-name fact goes back to `requests`. The version pin had only the bad source, so it stays quarantined. Plan steps and files are reworked by the agents that wrote them, in dependency order, under expiring leases. In the demo we kill the planner process with `kill -9` in the middle of its rework. A new process is refused while the lease is live and takes over once it expires. Quarantined memories are never deleted. They stay in the graph as history, and each replacement points at what it replaces.

## What "quarantined" means, and what it does not

Quarantined means the memory was **touched by** the flagged source through a recorded read. It does not mean the memory is wrong. We measured the gap with a counterfactual replay. We generated random crews (150 worlds for each of four world models, 1,340 world and document pairs per model), replayed each world as if the flagged document had never been ingested, and compared every memory with the graph's answer.

- On the recorded reads, no memory the source reached was left clean: 0 in 4,020 runs. This holds by construction, because the replay follows the same edges as the traversal. It shows the query does what it says, not that the recorded reads are complete.
- When an agent was influenced by something it never recorded (we model this as its whole context), the graph misses it: 7% of truly affected memories in our generated crews. **The guarantee is only as strong as the recorded reads.**
- About 63% of what it flags in those crews would have kept the same content without the source. The rule is cautious on purpose: a fact the poison merely voted on is still quarantined and then rebuilt from clean support.
- In the demo all six quarantined memories really change.

These numbers come from the 150-world run recorded in `docs/COUNTERFACTUAL.md`. A fresh 20-world run on the current code shows the same pattern: 0 misses on recorded reads, 60% to 66% of flags unchanged, and 9% missed under unrecorded influence.

## How we tried to break it

We did not trust our own tests. We ran ten AI attacker agents, each on one area: engine edge cases, multi-step sequences, crash consistency, the tool interface, web security, whether the page tells the truth, hostile input files, every claim in our docs, a fresh clone, and gaps in the specification. Three AI skeptics then checked each finding. They found real defects. Two would have made us say false things. A crash could leave a flagged document with nothing marked red. And our own evaluation ignored a fact's stored value, so it called the demo's poisoned fact a cautious flag when it really was poisoned. A second round attacked the fixes.

The fixes came with regression tests (36 of them are in `tests/test_attack_regressions.py`). On commit `b31ba1e` the full suite passes on Python 3.12, 3.13 and 3.14 (221 tests each), and an end-to-end check drives the real CLI through ten different worlds. A mutation check breaks the code 32 ways, one at a time. Its last full run caught 30. The two that survived are marked as equivalent mutants: another guard already blocks them.

## What it is not

- The agents in the demo are scripted. Their read sets are written in a fixture, not observed from a model.
- At 25 nodes a recursive SQL query could do the same traversal. The case for a graph is the shape of the problem, not speed: provenance is edges, the blast radius and the receipt are one query each, and the schema is the audit trail.
- Healing counts episodes, not independent documents. Planted documents nobody has flagged yet could outvote real ones.
- Memory repair cannot undo actions an agent already took outside the graph.

## What's next

Record reads at the source: route every agent read through a tool that writes the edge, so the 7% we miss on unrecorded influence shrinks. Then run it on a real agent workflow and compare it with restarting from a trusted checkpoint.

The README and `docs/COUNTERFACTUAL.md` have the setup, and every number above comes with the command that reproduces it. FalkorDB is source-available under SSPLv1. Our code is MIT.
