# Submission form text (copy and paste)

Every line below is backed by the README or a doc in this repo. Rules checked against https://www.wemakedevs.org/hackathons/falkordb/rules (deadline October 18, 11:59 PM IST = 2:29 PM EDT).

**Project name:** QUARANTINE

**Track:** Track 02, Agent Memory and Coordination

**One line:** When a source turns out to be poisoned, QUARANTINE follows the recorded reads in a FalkorDB graph to mark every agent memory that came from it, explains each one with a path back to the source, and rebuilds only that work.

**Description (short):**
A crew of agents (research, planner, coder) shares memory in FalkorDB. Every write records what it was written after reading, as an edge. When a document is flagged as prompt-injected, one Cypher traversal quarantines every memory whose recorded reads lead back to it: 6 of 25 in the demo, against 25 for resetting every agent it touched and 19 for rolling back by time. Each quarantined memory has a receipt (the path to the source, as a sentence). Facts are rebuilt from clean sources by strict plurality of at least two; plans and files are reworked by their authors in dependency order under expiring leases, and a real kill of an agent process is recovered. A fixed read-only tool catalog (MCP) answers in four shapes and never hands an agent a quarantined memory's text.

Limits we state up front: quarantined means "touched by through a recorded read", not "proven wrong"; in generated crews about 63% of what it flags would have kept the same content, and influence an agent never recorded is missed (7% of truly affected memories). The demo's agents are scripted. Details and rerun commands: docs/COUNTERFACTUAL.md.

**Why the graph does real work:** provenance is edges; the blast radius is one variable-length traversal, the receipt is one shortest-path query, and healing, task blocking and leases are graph state. Remove FalkorDB and nothing is left to quarantine, explain or repair.

**Repository:** https://github.com/Ps23102004/graphhacks-quarantine (must be public before submitting)

**Demo video:** (paste the link; 3:00 or less)

**Live deployment:** none; complete local setup in the README (Docker FalkorDB 6.0.2 + `uv`).

**Graph data model and Cypher:** README sections "How the graph works" and "Find affected memories"; every statement is in `quarantine/queries.py`.

**AI use disclosure:** We used Anthropic Claude and OpenAI models for architectural exploration, Cypher experiments, fixture generation, test scaffolding, attack and review passes, and documentation. The team ran, reviewed and validated the implementation against FalkorDB 6.0.2 (test suite, validation scripts, browser checks, fresh-clone runs on macOS and Windows).

**Team:** Parth Singh, Amandeep Kaushik, Aashna Tyagi

**Blog post:** docs/BLOG.md (publish wherever the form asks; it uses only the numbers above)

## Before pressing submit

- [ ] Repository is public, and the README renders on GitHub
- [ ] README line "Demo video" has the real link (replace VIDEO_LINK_GOES_HERE)
- [ ] Video is 3:00 or less and plays logged out
- [ ] `git rev-parse HEAD` of the submitted repo equals the tag that passed the checks
- [ ] Screenshot of the confirmation page sent to the team
