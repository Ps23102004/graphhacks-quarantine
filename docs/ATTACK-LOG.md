# Attack log

What the AI attacker agents reported, by title. This is a log of reports, not a proof of coverage. Each attacker ran the real code on its own scratch graph and had to give the commands and output. Three AI skeptics then tried to refute each finding of medium severity or worse (round 1 had 10 attackers; round 2 had 6 and attacked the fixes).

Status: every finding rated medium or worse was fixed (each with a regression test, mostly in `tests/test_attack_regressions.py`) or is written into the README's "Limits to keep in mind". Low-severity findings were not all fixed. Known leftovers: `tests/test_packaging.py` needs internet to install the wheel; two `session2` processes started at the same moment can take each other's lease; the held-out and counterfactual evaluations assume the recorded reads are the truth except in their one "unrecorded influence" row.

Severities are the attackers' own ratings.

## Round 1 (10 attackers)

### web-security

- [high] Page says 'Graph unreachable' (red down dot) when the graph does not exist yet, so the documented empty-graph banner never shows
- [low] No browser security headers (CSP, X-Content-Type-Options, frame-ancestors)

### engine-edge

- [critical] rework() DETACH DELETEs an existing clean memory whose id is <old>_v2, so its content is lost and its readers' provenance edges vanish; a later flag then misses them (silent false negative)
- [high] HEAL_FACTS CREATEs a second node with id f_v2 when an original fact f_v2 exists, so two Memory nodes share one id
- [high] Rejected dissent edges are walked as provenance: flagging a rejected voter's doc quarantines the healed fact and its rework, and the receipt says the fact was consolidated from that voter
- [medium] A quarantined, healable fact that nothing reads never heals: session2 exits with 'no rework tasks yet (run `quarantine flag DOC` first)' even though flag was run
- [medium] The plurality vote compares claim strings exactly, so 'requests' / 'Requests' / 'requests ' split the vote and a 2-vote minority wins the heal
- [medium] validate_fixture accepts worlds that load() then crashes on halfway, leaving a partly written graph
- [low] The engine counts a duplicated support entry once, the worldgen oracle counts it twice, so they disagree on heal
- [low] A step reading an artifact with an earlier tick is rejected as 'unknown memory', though the artifact exists

### cli-fixture-security

- [critical] A fixture memory id ending in _v2 is silently deleted or duplicated by rework/heal: data loss, wrong provenance, and a later flag misses poisoned work
- [high] session2 refuses to heal when the closure has no step/artifact, with a false error telling the user to run flag (which they did)
- [medium] validate_fixture misses many bad worlds; session1 deletes the existing graph, then crashes with a traceback, leaving a half-loaded or empty graph
- [medium] A duplicate memory id inside one section is silently accepted (last YAML key wins), so a clean episode can be replaced by a poisoned one without any error
- [medium] read_fixture input errors (missing file, directory, non-UTF8, empty file, YAML tags) surface as raw Python tracebacks
- [low] No type check on text: an 8 KB YAML alias bomb expands to a 10^7-element list that is printed and stored in the graph (520 MB RSS)

### mcp-answers

- [high] inspect_quarantined_memories always fails over MCP (return annotation list[dict] but returns a dict)
- [medium] mcp_inspect.py hides the real tool error behind 'unhandled errors in a TaskGroup'
- [low] MCP why_connected description says 'Weighted shortest path'; the code and docs say unweighted
- [low] An id over 256 characters that exists in the graph is answered 'does not resolve to a node'

### sequencing

- [high] Advisory whose closure has no step or artifact: the healable fact is never healed, and session2 says to run flag, which was already run
- [medium] A restarted session2 completes a task under the crashed process's still-live lease; the refused CLAIM is ignored and it prints 'wrote' for a write it did not make
- [medium] After a second advisory reaches the healed twins, the start-up query and status report already-replaced memories as unresolved or waiting
- [medium] status and session2 on a graph that does not exist crash with a raw redis traceback
- [low] A second flag prints a 'closure' list containing memories that have no path to that doc, and stamps twins with a quarantine_tick earlier than the tick they were written
- [low] unflag on a doc that was never flagged reports 'retracted advisory'

### atomicity

- [critical] If `flag` dies right after FLAG_DOC, the doc shows as flagged but no memory is red, and status reports complete: true
- [critical] If `unflag` dies after RESET_QUARANTINE, a doc that is still flagged has zero red memories, and session2 reports a fixpoint
- [high] If session2 dies right after CLAIM, every later session2 run fails, because the logical clock never passes the dead lease
- [medium] After a torn unflag, why_quarantined says a memory 'reaches flagged doc_5' when doc_5 is no longer flagged
- [medium] If session1 dies between a memory's node and its read-set edges, the poisoned artifact stays clean after flag and every audit query returns 0
- [low] If `flag` dies after CREATE_REWORK_TASKS, tasks have no BLOCKED_BY edges and session2 skips the dependency order

### spec-blindspots

- [critical] The counterfactual ignores each Fact's stored value, so it scores the demo's own poisoned fact as a 'needless flag' and the docs then say something false about it
- [high] '0 false negatives in 4,020 runs' cannot fail: the ground truth is built from the same declared edges as the closure, and graph, oracle and counterfactual all call poisoned memories clean
- [high] The loader silently drops declared provenance on Facts and Episodes, and never checks a Fact's value against its support: a silent false negative
- [medium] README says the harness captures each agent's read set before every write, but no capture exists; reads through the shipped MCP tools leave no trace
- [medium] After a second advisory, recovery status says complete: true with no warnings while 5 'clean' replacements are '[needs regeneration]' placeholders
- [low] After an advisory that follows a heal, the counters compare unlike sets, and STARTUP keeps showing a finished task as waiting

### page-truth

- [critical] With two flagged docs the headline says 'no source is flagged' and the banner names only one advisory
- [critical] After a partial unflag the Quarantined list keeps memories that are now clean, and clicking one returns not_in_graph
- [high] A selected receipt and its highlighted path stay on screen after the advisory behind them is retracted
- [high] The policy note is computed only on click and goes stale on poll, claiming hatched memories that are not drawn
- [medium] Torn flag (doc flagged, closure not run): headline says '0 of 25 reached by doc_7' while the wipe counters say 25 and 19
- [medium] A graph that does not exist yet shows 'Graph unreachable' and 'Connecting…' forever instead of the empty-state hint
- [low] The headline's agent count never shrinks: '6 agents' after switching to a 3-agent fixture with the page open
- [low] Empty-state and banner text claim things that are false in reachable states

### fresh-clone

- [high] scripts/validate_compose.sh (the automated compose check named in INSTRUCTIONS-TEAM) requests /vendor/vis-network.min.js, which no longer exists, so it aborts at step 5
- [medium] Test and validation counts in the docs are stale: 52 passed / 52/52 / 22 passed, vs observed 95 and 29; README contradicts TESTING.md
- [low] TESTING.md says validate.sh clones committed HEAD and 'Uncommitted work is not validated'; the script actually copies the working tree, uncommitted edits included
- [low] Docs reference files that are not in the repo: PLAN.md, plans/graphhacks-quarantine/PLAN.md, DAY1-SPIKES.md, docs/REVIEW-FINDINGS.md
- [low] The test suite needs internet: test_packaging pip-installs the wheel's dependencies from PyPI, so an offline run gives 1 failure
- [low] pytest is a runtime dependency: installing the wheel pulls pytest into the user's environment
- [low] The --fixture fixtures/support-crew.yaml example in the CLI help fails outside the checkout: that fixture is not in the wheel, the sdist or the Docker image

### claims-audit

- [high] COUNTERFACTUAL.md says f_http_client is a 'conservative flag that heals back to the same value', but it is the poisoned fact itself (reqeusts -> requests). A test asserts the false claim
- [high] The MCP tool inspect_quarantined_memories always fails over the real MCP protocol (annotated list[dict], returns dict). GUIDELINE-CONFORMANCE claims every tool answers in a shape
- [high] Stale test and check counts across the docs: '52 passed' (actual 95), validate '22 passed' (actual 29), '22 mutations / one equivalent' (actual 30 / 2)
- [medium] The docs contradict each other on the closure depth: TESTING and VALIDATION say 'bounded at depth 10', but the README and the code are unbounded
- [medium] The README mermaid diagram shows f_http_client consolidated from ep_1, ep_2, ep_3. The real support is ep_2, ep_5, ep_8 (+ ep_7a)
- [medium] TESTING and VALIDATION say validate.sh validates committed HEAD only. The script actually tars the working tree, including uncommitted edits
- [medium] Several docs still describe the removed UI (hive plot, dark ground, vis-network, squares and rows, orange path, footer) and cite a missing DAY1-SPIKES.md. Video length is 3:00 in one doc and 2:45 in another
- [low] INSTRUCTIONS-TEAM tells the voiceover to claim graph closures 'beat 10 lines of Python or SQLite CTEs', which README and AGENTS.md disown. VALIDATION's status rows are stale

## Round 2 (6 attackers, on the fixed build)

### tools and MCP

- [high] trace_provenance_receipt says a memory 'reaches flagged doc_7' when doc_7 is no longer flagged (torn unflag), and says 'no provenance path to any flagged document' when one exists (torn flag)
- [medium] 'unknown ... does not resolve to a node' is said of real nodes, including a quarantined memory
- [medium] recall hands an agent the poisoned content of a quarantined memory as its 'answer', even after it has a clean replacement
- [low] Wrong-typed or missing arguments return MCP errors, not one of the four shapes; the in-function type guards are dead code
- [low] get_recovery_status reports a non-graph Redis key or a query failure as 'no recovery_status implementation found / not yet implemented'
- [low] Recovery status is stamped 'as of tick 33' while it already reflects the advisory flagged at tick 40
- [low] An unknown answer echoes an over-length id back twice in full (2 MB in, about 4 MB out) and gives a misleading reason for NUL ids

### hostile inputs

- [critical] A world validate_fixture accepts but FalkorDB cannot store makes session1 delete the existing graph, then crash with a redis traceback
- [high] A fixture can preset the harness's s1.complete marker, so a crashed load is accepted as finished and flag runs on a partial graph
- [medium] Unhashable YAML keys and a list-valued agent end in a Python traceback, not a one-line error
- [medium] Hostile flag:/rework:/procedure: sections are not validated: tracebacks, misprinted reads, and a negative lease that aborts session2
- [medium] Steps listed out of tick order, or a step that reads an artifact, are refused with a false 'unknown memory' message
- [low] YAML merge keys (<<: *anchor) are refused as 'not valid YAML'
- [low] Ids longer than 256 characters load and get quarantined, but every answer tool then calls them 'unknown memory'
- [low] The unknown-key error says 'note' is read, but memory notes are silently dropped

### crash consistency

- [high] session2 dies after HEAL, then a second advisory reaches the healed twin: rework_step_3 and rework_a_requirements stay blocked forever, yet session2 prints 'fixpoint'
- [high] The logical clock never advances across runs, so a crash after the --kill-planner lease takeover leaves rework_step_3 permanently unclaimable
- [high] status says complete: true with no warnings for a Session 1 that was killed halfway (8 of 25 memories)
- [high] Torn unflag: the receipt says a memory 'reaches flagged doc_5' when doc_5 is not flagged, and the page counter says 7 reached by doc_7 when doc_7's closure is 6
- [medium] Retrying an interrupted unflag says 'not flagged; nothing to retract' and leaves the torn red set in place
- [low] The CLAIM resume clause lets a second concurrent `quarantine session2` take a live lease, because every run uses session 's2'

### page truthfulness

- [critical] A second advisory after healing quarantines the healed twins, but the page still shows them as green healed replacements 'rebuilt from clean sources', and the headline reads '14 of 25'
- [high] Graph-derived placeholder twins ('[needs regeneration: ...]') are shown as 'rebuilt from clean sources' and in the Key's 'healed replacement' style

### claims audit

- [high] The blog image the checklist names still says 'Precise forgetting' and 'Graph-precise quarantine: only what the source actually reached'
- [medium] The held-out eval, the counterfactual eval and the mutation check test TAINT_CLOSURE, not FLAG_AND_CLOSE, which is the statement the CLI actually runs
- [medium] VALIDATION.md problem statement says 'quarantine exactly the memories it influenced'
- [medium] CHECKLIST-AASHNA tells the tester to call an MCP tool that does not exist
- [medium] The counterfactual step in CHECKLIST-AASHNA expects '0 false negatives', but the script prints nonzero in that column every time
- [medium] MCP get_recovery_status says 'not yet implemented' when the real problem is a graph error
- [low] docs/TESTING.md has a stale atomicity limit, an all-interfaces docker command and a stale list of test graphs
- [low] Smaller stale or loose sentences: an open item that is now fixed, a hop-bound docstring and 'ten agents' with nine categories listed

### multi-advisory sequences

- [critical] Page paints quarantined healed twins green as 'healed replacement', counts them as 'rebuilt from clean sources', mixes twins into the 'N of 25' headline, and leaves the real clean twins-of-twins off the graph
- [high] Healing is order-dependent: a second advisory after healing loses the outvoted clean majority, so a fact the README rule says can be rebuilt stays dead (and its readers are rebuilt ungrounded)
- [medium] After a second advisory, recovery_status and the session2 start-up lines report resolved originals as 'unresolved' and done tasks as 'waiting_on' red blockers
- [low] Second flag's comparison line counts twins in 'quarantined' but excludes them from both baselines
