# Forgetting one bad source without wiping the clean work

*Graph Hacks 2026, Track 02 (Agent Memory and Coordination). Team: Parth Singh, Amandeep Kaushik, Aashna Tyagi.*

![The provenance ledger: a receipt path from a quarantined requirements file back to the poisoned document](media/hive-receipt.png)

## The problem

Give a crew of agents a shared memory and a single poisoned web page can travel a long way. In our demo a forum thread tells the research agent that the Python package `requests` is now called `reqeusts`, a typosquat. Research turns that into a fact. The planner reads the fact and writes a plan step. The coder reads the plan and writes `requirements.txt`. The coder never saw the forum thread, but its file is poisoned anyway.

When the advisory finally lands ("that thread was a prompt injection"), what do you throw away? Teams usually do one of two things. They reset every agent that touched the poison, or they roll memory back to before the bad document arrived. In our demo world of 25 memories, the first throws away all 25 and the second throws away 19. Most of that was clean work.

## What we built

QUARANTINE keeps the crew's memory in FalkorDB. Every memory is a node: an episode extracted from a document, a fact consolidated from episodes, a plan step, a file. Every write records what it was written after reading, as an edge. So "what did this poison reach?" stops being a guess and becomes one traversal:

```cypher
MATCH (d:Doc {id: $doc})<-[:EXTRACTED_FROM|CONSOLIDATED_FROM|INFLUENCED_BY*1..]-(m:Memory)
SET m.quarantined = true
```

In the demo that marks 6 of the 25 memories. Click any of them and the page shows the receipt, the path back to the source, as a sentence: the requirements file was written after reading step 3, which was written after reading the HTTP client fact, which was consolidated from an episode, which was extracted from the poisoned thread.

Then the crew repairs itself. A fact is rebuilt only from clean episodes, and only when at least two of them agree and that claim beats every other claim. The HTTP client fact goes back to `requests`. Plan steps and files are reworked by their own authors, in dependency order, under expiring leases. We kill the planner process for real in the middle of its repair; a new process is refused while the lease is live and takes over once it expires. Nothing is deleted. The poisoned lineage stays in the graph as history, and every replacement points at what it replaces.

## What "quarantined" means, and what it does not

This is the part we care about most, because a tool that decides what to forget must not overstate itself.

Quarantined means **touched by** the flagged source through a recorded read. It does not mean proven wrong. We measured the gap with a counterfactual replay: for thousands of randomly generated crews, we reran each world with the flagged document never ingested and compared every memory with the graph's answer.

- On the recorded reads, no memory the source reached was left clean. That holds by construction, because the replay follows the same edges, so we do not sell it as more than it is.
- When an agent was influenced by something it never recorded (we model this as its whole context), the graph misses it: 7% of truly affected memories in our generated crews. **The guarantee is exactly as strong as the recorded reads.**
- About 63% of what it flags in those crews would have kept the same content without the source. Provenance is cautious: a fact the poison merely voted on is still quarantined and then rebuilt from clean support.
- In the demo all six quarantined memories really change.

## How we tried to break it

We did not trust our own tests. Ten independent attacker agents went after the engine, crash consistency, the tool interface, web security, the page's honesty, hostile input files, every claim in our docs, a fresh clone and the specification itself, and three skeptics checked every finding. They found real defects, including two that would have made us say false things: a crash could leave a flagged document with nothing marked red, and our own evaluation mislabelled the demo's poisoned fact as a cautious flag. A second round attacked the fixes. Every confirmed finding is now a regression test. The final build passes the suite on Python 3.12, 3.13 and 3.14, an end-to-end check on ten different worlds, and a mutation check that breaks the code thirty ways and confirms a test catches each one.

## What it is not

The agents in the demo are scripted; their read sets are written in a fixture, not observed from a model. At 25 nodes a recursive SQL query could do the same traversal; the case for a graph is the shape of the problem (provenance is edges, the blast radius and the receipt are one query each, the schema is the audit trail), not speed. Healing counts episodes, not independent documents, so planted documents nobody has flagged yet could outvote real ones. And memory repair cannot undo actions an agent already took outside the graph.

## What's next

Record reads at the source: route every agent read through a tool that writes the edge, so the 7% we miss on unrecorded influence goes toward zero. Then run it on a real agent workflow and compare it with restarting from a trusted checkpoint.

Code, setup and every number above with the command that reproduces it: the repository README and `docs/COUNTERFACTUAL.md`. FalkorDB is source-available under SSPLv1; our code is MIT.
