# Submission form text (copy and paste)

Every line below is backed by the README or a doc in this repo. Rules checked against https://www.wemakedevs.org/hackathons/falkordb/rules (submissions close October 18, 11:59 PM IST, which is 2:29 PM EDT).

**Project name:** QUARANTINE

**Track:** Track 02, Agent Memory and Coordination

**One line:** When a source turns out to be poisoned, QUARANTINE follows the recorded reads in a FalkorDB graph, marks every agent memory they connect to that source, explains each one with a path back to it, and rebuilds only that work.

**Description (short):**
Three agents (research, planner, coder) share memory in FalkorDB. Every write records, as edges, what the agent read before writing it. When a document is flagged as prompt-injected, one Cypher traversal quarantines every memory whose recorded reads lead back to it. In the demo that is 6 of 25 memories. Resetting every agent it touched would discard 25, and rolling back by time would discard 19. Each quarantined memory has a receipt: the path to the source, written as a sentence. A fact is rebuilt only when at least two clean episodes agree and their claim has more votes than any other. Plan steps and files are reworked by their authors in dependency order under expiring leases. In the demo we kill the planner process with `kill -9` mid-task, and a new process takes over once the lease expires. A fixed, read-only MCP tool catalog answers in four shapes, and its recall and inspect tools withhold a quarantined memory's text.

Limits we state up front. Quarantined means "touched by, through a recorded read", not "proven wrong". In generated crews about 63% of what it flags would have kept the same content, and it misses influence an agent never recorded (7% of truly affected memories). The demo's agents are scripted. Details and rerun commands: docs/COUNTERFACTUAL.md.

**Why the graph does real work:** provenance is edges. The blast radius is one variable-length traversal, the receipt is one shortest-path query, and healing, task blocking and leases are graph state. Remove FalkorDB and there is nothing left to quarantine, explain or repair.

**Repository:** https://github.com/Ps23102004/graphhacks-quarantine (must be public before submitting)

**Demo video:** (paste the link; our target is 3:00 or less, the rules set no length)

**Live deployment:** none. Complete local setup is in the README (Docker FalkorDB 6.0.2 and `uv`).

**Graph data model and Cypher:** README sections "How the graph works" and "Find affected memories". Every statement is in `quarantine/queries.py`.

**AI use disclosure:** We used Anthropic Claude and OpenAI models for architectural exploration, Cypher experiments, fixture generation, test scaffolding, attack and review passes, and documentation. The team ran, reviewed and validated the implementation against FalkorDB 6.0.2 (test suite, validation scripts, browser checks, fresh-clone runs on macOS and Windows).

**Team:** Parth Singh, Amandeep Kaushik, Aashna Tyagi

**Blog post:** docs/BLOG.md (publish wherever the form asks; its numbers come from the README and docs/COUNTERFACTUAL.md)

## Before pressing submit

- [ ] Repository is public, and the README renders on GitHub
- [ ] README line "Demo video" has the real link (replace VIDEO_LINK_GOES_HERE)
- [ ] Video plays logged out (team target: 3:00 or less)
- [ ] `git rev-parse HEAD` of the submitted repo equals the tag that passed the checks
- [ ] Screenshot of the confirmation page sent to the team
