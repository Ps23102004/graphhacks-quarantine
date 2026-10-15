# QUARANTINE — shared agent memory that heals itself

Graph Hacks 2026 (FalkorDB × WeMakeDevs), Track 02: Agent Memory and Coordination.

A crew of three agents (Research+Consolidator, Planner, Coder) shares one FalkorDB
graph as its memory. The harness records what each agent read before each write.
When one ingested document turns out to be prompt-injected, one traversal quarantines
exactly the memories it influenced across agents and sessions, a `shortestPath` is the
receipt for each one, and facts that still have clean support are re-consolidated so
the crew can redo only the poisoned work, in dependency order.

## Run the numbers

```bash
docker run -d --name quarantine-falkordb -p 6379:6379 -p 3000:3000 \
  falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
uv sync
uv run pytest -q                              # asserts every number the demo says
uv run python spikes/verify_queries.py        # prints every hero query with its output
```

- `fixture.yaml` — the demo world (8 docs, 25 memories, 3 agents, explicit read sets) and every expected number.
- `quarantine/queries.py` — every Cypher statement, named.
- `quarantine/loader.py` — fixture loader + the rework write (with the no-re-poisoning guard).
- `spikes/` — Day-1 spike script and raw results against the pinned image.

FalkorDB is source-available (SSPL); the image above is the one every number here was produced on.
