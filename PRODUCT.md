# PRODUCT.md — Quarantine

Assumptions inferred from the team's brief and the 2026-10-17 conversation; confirm or correct.

- **What it is:** shared graph memory for a crew of AI agents that can forget one bad source precisely. Before every write the harness records what the agent read as edges in FalkorDB; when a source is flagged as prompt-injected, one traversal quarantines exactly the memories it influenced, a path is the receipt, facts heal from clean sources, and repair runs in dependency order with leases.
- **Who looks at it:** hackathon judges (Graph Hacks 2026, Track 02) opening the web app on a laptop, and viewers of a 3-minute screen-recorded video. Most are engineers; few are graph-database experts.
- **What they must understand in 90 seconds:** "6 of 25, not 25 or 19", why a memory is red (the path), and that the crew repairs itself.
- **Mode:** Operate (a live inspection tool) with one authored moment (the red wave).
- **Brand commitments (from the founder):** originally a "hive mind" look; shipped as a printed provenance ledger (see DESIGN.md): chips and ribbons, a red ink spill, a yellow highlighter receipt; Apple-like restraint and system type; not boring, not plain lines.
- **Truth constraints:** agents are scripted (say so); every number on screen comes from the graph or the server, never hard-coded; demo data is synthetic and labelled as such in the README.
- **Platforms:** desktop browser first (1440 to 1920 wide), usable at 375 wide; light newsprint ground, so it reads in a bright room and in a screen recording.
