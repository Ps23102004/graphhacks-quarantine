# Instructions and work split: Team Parth Singh
**Project: QUARANTINE (Graph Hacks 2026, Track 02: Agent Memory and Coordination)**
**Written:** Friday Oct 16, 2026 | **Submission target:** Sunday Oct 18, 12:00 EDT

**Status Sun 2026-10-18:** Aashna reported twice (Oct 16 and Oct 18) and Aman rewrote the README (Oct 17). Parth ran a fresh GitHub clone with Claude on Oct 18 (221 tests, ten worlds, compose check, demo path, junk MCP input). The blog draft (`docs/BLOG.md`) and submission text (`docs/SUBMISSION.md`) were written by Parth with Claude. The demo video is recorded and public: https://youtu.be/BZ3Qp1WWYB8 (2:51). See `docs/TEAM.md` for the full status.

---

## 1. What we are building and how it works

QUARANTINE is a prototype for tracing and repairing shared agent memory in FalkorDB. A crew of agents (`research`, `planner`, `coder`) writes memories across two sessions. If one source turns out to be a prompt injection or otherwise bad, work built on it can carry the damage downstream. When the source is flagged, the graph marks every memory whose recorded reads lead back to it.

The agents are scripted: their outputs and read sets come from `fixture.yaml`. The graph writes, the closure, the healing, the task blocking and the leases are real. In Session 2 they behave like this:

1. **Research (`research`):**
   - **Writes:** `Episode` nodes extracted from source documents, consolidated into `Fact` nodes.
   - **Healing rule:** a quarantined fact is rebuilt only when at least 2 clean episodes agree and their claim has more votes than any other claim (strict plurality). In the demo, 3 clean episodes say `requests` against the poisoned `reqeusts`, so `f_http_client_v2` supersedes `f_http_client` (`SUPERSEDES` edge). The quarantined originals stay in the graph as history.
2. **Planner (`planner`):**
   - **Writes:** `PlanStep` nodes.
   - **Readiness rule:** a rework task waits while it is `BLOCKED_BY` a quarantined memory that has no clean replacement. The planner claims it only when the task is ready.
3. **Coder (`coder`):**
   - **Writes:** `Artifact` nodes (files) based on plan steps.
   - **Write guard:** a replacement write is refused if its read set cites a missing or quarantined memory (`loader.rework`). In the demo the coder's task waits on `step_3` until the planner has written `step_3_v2`.

---

## 2. Aashna's work package (testing and infrastructure)

**Goals:** verify a fresh setup, test Docker Compose, and check the MCP server.

### Tasks
1. **Clone and run on your machine:**
   ```bash
   git clone https://github.com/Ps23102004/graphhacks-quarantine.git && cd graphhacks-quarantine
   docker run -d --name quarantine-falkordb -p 127.0.0.1:6379:6379 -p 127.0.0.1:3000:3000 \
     falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
   uv sync --all-extras
   uv run pytest -q  # must end with 0 failed (the count changes; see docs/RUNS.md)
   ```
2. **Verify the Docker Compose setup:**
   - Run `bash scripts/validate_compose.sh`. It builds the stack on port 8777, checks the page responds, recreates the containers and checks the data survived. Expect `Compose validation complete: ALL PASS`.
   - Or by hand: `docker compose -f deploy/docker-compose.yml up -d`, then open http://localhost:8765 and check the page loads.
3. **MCP server check:**
   - `uv run python scripts/mcp_inspect.py list` starts `quarantine/mcp_server.py` over stdio and lists the six tools.
   - `uv run python scripts/mcp_inspect.py call inspect_quarantined_memories` and `uv run python scripts/mcp_inspect.py call trace_provenance_receipt '{"memory_id": "a_requirements"}'` show that an external agent can audit the graph through MCP (run the demo `flag doc_7` first).

---

## 3. Aman's work package (documentation, compliance and video script)

**Goals:** README polish, the rules check, and the blog post.

### Tasks
1. **Rules and release check:**
   - The repo has an MIT `LICENSE` and has been public since Oct 18.
   - Search the code for leaked API keys, tokens or local absolute paths.
   - Terminology: FalkorDB is **source-available (SSPL)**, not "open source".
2. **Review the `README.md`:**
   - The Mermaid schema, the 6 vs 25 vs 19 comparison and the quickstart commands should be clear to someone seeing the project for the first time.
   - Keep the "AI assistance" section.
3. **Video rehearsal (`docs/DEMO-SCRIPT.md`):**
   - Walk through the script; the video must be 3:00 or less.
   - Points the voiceover should make:
     - *Pain:* "Don't wipe 25 memories when the bad source reached 6."
     - *Why a graph:* provenance is edges, and the closure and the receipt are one query each. At 25 nodes a recursive SQL query or a Python set does the same work, so the case is the shape of the problem, not speed (README, "Limits to keep in mind").
     - *Stunt:* a real `kill -9` of the planner process, then another process takes over its expired lease.
4. **Blog post:** drafted by Parth with Claude in `docs/BLOG.md` ("Forgetting one bad source without wiping the clean work"). It covers:
   1. Why resetting agents or rolling back destroys clean work.
   2. Recording each write's reads as edges.
   3. The receipt: the path from a quarantined memory back to the source.
   4. Healing facts from clean support, how we tested it, and the limits.

---

## 4. Parth's work package (recording and submission)

1. Record the demo with a split screen: terminal on the left (`quarantine session1 --slow 0.4`, `flag doc_7`, `session2 --kill-planner`), the page on the right (http://localhost:8765).
2. Cut the video to 3:00 or less, add captions, and upload it unlisted to YouTube.
3. Fill in and submit the WeMakeDevs submission form before Sunday 12:00 EDT.
