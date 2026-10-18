# PRODUCT.md: Quarantine

Notes on who the page is for and what it must show, written on 2026-10-17 from the team brief.

- **What it is:** shared graph memory for a crew of AI agents. It can forget one bad source without wiping clean work. Each write is stored with the reads declared in `fixture.yaml`, as edges in FalkorDB. When a source is flagged as a prompt injection, one query quarantines every memory whose recorded reads lead back to it. A path is the receipt. Facts are rebuilt from unquarantined episodes, and rework runs in dependency order with leases. The agents in the demo are scripted.
- **Who looks at it:** Graph Hacks 2026 judges (Track 02) opening the page on a laptop, and people watching a video of at most 3 minutes. Most are engineers. Few are graph-database experts.
- **What they must get in 90 seconds:** 6 of 25 memories are quarantined, not 25 or 19. Why a memory is red (the path). Scripted agents rework the flagged memories in dependency order.
- **Mode:** a live inspection tool with one staged moment, the red ink spreading.
- **Look (Parth's brief):** first a "hive mind" look. What shipped is a printed provenance ledger (see DESIGN.md): chips and ribbons, red ink for contamination, a yellow highlighter for the receipt. Restrained type. Not plain lines.
- **Truth rules:** the page says the agents are scripted. Every chip, ribbon and number on the page is read from FalkorDB through the server, never hard-coded. The README says the demo actions are scripted.
- **Platforms:** desktop browser first. `scripts/check_browser.js` checks the layout at 1920, 960 and 375 wide. Light newsprint background, so it reads in a bright room and in a screen recording.
