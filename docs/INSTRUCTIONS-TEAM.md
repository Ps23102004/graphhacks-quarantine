# Instructions & Work Distribution: Team Parth Singh
**Project: QUARANTINE (Graph Hacks 2026, Track 02: Agent Memory & Coordination)**
**Updated:** Friday Oct 16, 2026 | **Submission Target:** Sunday Oct 18, 12:00 EDT

---

## 1. What Are We Building & How It Works (For the Whole Team)

QUARANTINE is a self-healing shared memory layer for multi-agent systems built directly on FalkorDB.
When multi-agent crews (`Research`, `Planner`, `Coder`) collaborate across sessions, an ingested prompt injection or bad source contaminates downstream agent work.

### How Our Agents Make Decisions:
1. **Research Agent (`research`):**
   - **What it does:** Reads source docs, extracts `Episode` nodes, and consolidates them into `Fact` nodes.
   - **Decision policy:** Plurality consensus. To establish or heal a `Fact`, it requires $\ge 2$ agreeing clean source episodes. If a bad document introduces a fake version or renamed library, but 3 clean docs say otherwise, Research uses topological voting to supersede the tainted fact with a clean twin (`SUPERSEDES` edge) and leaves orphaned poison nodes quarantined as auditable history.
2. **Planner Agent (`planner`):**
   - **What it does:** Generates `PlanStep` nodes in logical sequence.
   - **Decision policy:** Causal readiness gate. Before claiming rework on a step, it queries FalkorDB for active `BLOCKED_BY` dependencies. If an upstream fact is poisoned and has no clean replacement head, Planner refuses to execute and remains in `blocked` state.
3. **Coder Agent (`coder`):**
   - **What it does:** Generates `Artifact` code/config files based on PlanSteps.
   - **Decision policy:** Causal isolation guard. Coder will fail if an emitted write references an unreplaced tainted memory. It only unblocks when Planner has verified clean dependencies.

---

## 2. Aashna's Work Package (Graph Engineering & Infrastructure)

**Primary Goals:** Verify fresh deployment, test Docker compose, and run S13–S16 spikes.

### Concrete Tasks:
1. **Clone & Clean Run on Your Machine:**
   ```bash
   git clone <repo-url> && cd graphhacks-quarantine
   docker run -d --name quarantine-falkordb -p 6379:6379 -p 3000:3000 \
     falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
   uv sync --all-extras
   uv run pytest -v  # Must pass 52/52 tests
   ```
2. **Verify Docker Compose Deployment:**
   - Test `deploy/docker-compose.yml`:
     ```bash
     docker compose -f deploy/docker-compose.yml up -d
     ```
     Or run `bash scripts/validate_compose.sh` for automated test with container recreate and persistence check.
   - Verify `http://localhost:8765` opens and responds with the live web viewer.
3. **FalkorDB Spike Check (S13 & S15):**
   - Check index performance on FalkorDB 6.0.2:
     ```cypher
     CREATE INDEX FOR (m:Memory) ON (m.id)
     CREATE INDEX FOR (d:Doc) ON (d.id)
     ```
   - Verify that Cypher queries in `quarantine/queries.py` properly use the index without syntax regressions.
4. **FastMCP Server Verification:**
   - Run `quarantine/mcp_server.py` and test tool calls (`inspect_quarantined_memories` and `trace_provenance_receipt`) to confirm an external agent can audit Quarantine memory via MCP.

---

## 3. Aman's Work Package (Documentation, Compliance & Video Scripting)

**Primary Goals:** Pitch polish, hackathon compliance check, and drafting the side-prize blog post.

### Concrete Tasks:
1. **Hackathon Compliance Review:**
   - Ensure the repository is ready for public release with MIT `LICENSE`.
   - Audit code for any leaked API keys, tokens, or local absolute paths.
   - Confirm terminology: FalkorDB is **source-available (SSPL)**, not "open source".
2. **Review & Polish `README.md`:**
   - Ensure the Mermaid schema, the "6 vs 25 vs 19" hook, and the quickstart commands are clear to someone seeing the project for the first time.
   - Include the AI Disclosure section already added to the README.
3. **Video Rehearsal (`docs/DEMO-SCRIPT.md`):**
   - Walk through the exact 2-minute 45-second script.
   - Ensure the voiceover emphasizes:
     - *Pain:* "Don't fire the company over one phish; don't wipe 25 memories when only 6 are sick."
     - *FalkorDB Moat:* Why recursive graph closures beat 10 lines of Python or SQLite CTEs.
     - *Stunt:* The real `kill -9` Planner failover demonstrating graph-native lease mechanics.
4. **Draft the AirPods Side-Prize Blog Post:**
   - Title: *"We Poisoned Our Agents' Memory On Purpose: Self-Healing Multi-Agent Architecture with FalkorDB"*
   - Structure from `PLAN.md` Section 7:
     1. Why resetting agents destroys clean work.
     2. Storing read sets as `INFLUENCED_BY` graph edges.
     3. Backward traversal reachability and `shortestPath` receipts.
     4. Plurality healing from clean support.

---

## 4. Parth's Work Package (Recording, Frontend Integration & Final Submission)

1. Run the live demo recording with screen split: Terminal on the left (`quarantine session1 --slow 0.4`, `flag doc_7`, `session2 --kill-planner`), web UI on the right (`http://localhost:8765`).
2. Cut video to $\le 2:45$, add captions, upload unlisted to YouTube.
3. Fill and submit the WeMakeDevs project submission form before Sunday 12:00 EDT.
