"""Every Cypher statement QUARANTINE runs, named. Verified against
falkordb/falkordb:6.0.2 (spikes/DAY1-SPIKES.md); verdicts and sample output in
plans QUERIES.md. Keep this file the single source of truth for the demo, the
MCP tool descriptions and the README.

Conventions: $doc flagged document id; $tick logical clock; $session session
id; $me agent name. Memories are never deleted: quarantine is a flag, repair is
a new memory with a SUPERSEDES edge, so the poisoned lineage stays as history.
"""

# ---------------------------------------------------------------- Session 2: flag + closure
FLAG_DOC = """
MATCH (d:Doc {id: $doc})
SET d.flagged = true, d.flag_reason = $reason, d.flag_tick = $tick
RETURN d.id
"""

# Q1 hero: everything whose provenance reaches the flagged doc. One traversal,
# three edge types, any depth up to 10. Returns the "precise" count.
TAINT_CLOSURE = """
MATCH (d:Doc {id: $doc})<-[:EXTRACTED_FROM|CONSOLIDATED_FROM|INFLUENCED_BY*1..10]-(m:Memory)
SET m.quarantined = true, m.quarantine_tick = $tick
RETURN count(DISTINCT m) AS precise, collect(DISTINCT m.id) AS ids
"""

# Q2 baseline: "reset the compromised agent". Every memory authored by any agent
# that authored anything in the closure.
NAIVE_PER_AGENT = """
MATCH (d:Doc {id: $doc})<-[:EXTRACTED_FROM|CONSOLIDATED_FROM|INFLUENCED_BY*1..10]-(:Memory)<-[:AUTHORED]-(a:Agent)
WITH DISTINCT a
MATCH (a)-[:AUTHORED]->(all:Memory)
RETURN count(DISTINCT all) AS naive, collect(DISTINCT a.name) AS agents_wiped
"""

# Q2b baseline: "invalidate everything written after the bad doc came in"
# (what a time-based memory store can do). Kills clean work too.
NAIVE_TIME_BASED = """
MATCH (d:Doc {id: $doc})<-[:EXTRACTED_FROM]-(e:Episode)
WITH min(e.tick) AS t0
MATCH (m:Memory) WHERE m.tick >= t0
RETURN count(m) AS naive_time, t0
"""

# Q3 hero: the receipt. Why is THIS artifact red? FalkorDB only allows
# shortestPath in WITH/RETURN (spike S2a), never in MATCH.
RECEIPT = """
MATCH (a:Memory {id: $from}), (d:Doc {id: $doc})
WITH shortestPath((a)-[:INFLUENCED_BY|CONSOLIDATED_FROM|EXTRACTED_FROM*..10]->(d)) AS p
RETURN [n IN nodes(p) | n.id] AS hops, length(p) AS len, [r IN relationships(p) | type(r)] AS via
"""

# Q3b same receipt through the algorithm procedure (sponsor feature on screen).
RECEIPT_SPPATHS = """
MATCH (a:Memory {id: $from}), (d:Doc {id: $doc})
CALL algo.SPpaths({sourceNode: a, targetNode: d,
                   relTypes: ['INFLUENCED_BY', 'CONSOLIDATED_FROM', 'EXTRACTED_FROM'],
                   maxLen: 10, pathCount: 1})
YIELD path, pathWeight
RETURN [n IN nodes(path) | n.id] AS hops, pathWeight AS len
"""

# Q4a after the closure: how much clean support does each Fact still have, and
# which quarantined memories can ever be repaired. Episodes from a flagged doc
# never heal; a Fact heals only with >= 2 clean episodes; steps and artifacts
# are reworked by their author once their healable inputs are superseded.
SUPPORT_AND_HEALABLE = """
MATCH (m:Memory)
OPTIONAL MATCH (m)-[:CONSOLIDATED_FROM]->(e:Episode) WHERE NOT e.quarantined
WITH m, count(e) AS clean
SET m.support_clean = CASE WHEN m:Fact THEN clean ELSE null END,
    m.healable = CASE WHEN NOT m.quarantined THEN null
                      WHEN m:Episode THEN false
                      WHEN m:Fact THEN clean >= 2
                      ELSE true END
RETURN m.id, m.support_clean, m.healable
ORDER BY m.tick
"""

# Q7 rework ordering: one Task per quarantined step/artifact, BLOCKED_BY the
# quarantined inputs that can still heal (dead inputs block nothing: the rework
# proceeds without them).
CREATE_REWORK_TASKS = """
MATCH (m:Memory {quarantined: true}) WHERE m:PlanStep OR m:Artifact
MERGE (t:Task {id: 'rework_' + m.id})
  ON CREATE SET t.kind = 'rework', t.state = 'blocked', t.created_tick = $tick
MERGE (t)-[:REWORKS]->(m)
RETURN t.id ORDER BY t.id
"""
CREATE_BLOCKED_BY = """
MATCH (t:Task {kind: 'rework'})-[:REWORKS]->(m:Memory)-[:INFLUENCED_BY]->(x:Memory {quarantined: true, healable: true})
MERGE (t)-[:BLOCKED_BY]->(x)
RETURN t.id, collect(x.id) AS blocked_by ORDER BY t.id
"""

# Q4b hero: the Consolidator's heal. For every healable quarantined Fact with
# no replacement yet, re-consolidate from its clean episodes (majority claim),
# create the replacement, link it to the same clean support, SUPERSEDES the
# poisoned one. Pure Cypher: no LLM decides what "clean" means.
HEAL_FACTS = """
MATCH (f:Fact {quarantined: true, healable: true})-[c:CONSOLIDATED_FROM]->(e:Episode)
WHERE NOT (f)<-[:SUPERSEDES]-() AND NOT e.quarantined
WITH f, c.claim AS claim, collect(e) AS eps ORDER BY size(eps) DESC, claim
WITH f, collect({claim: claim, eps: eps}) AS groups
WITH f, groups[0].claim AS best, reduce(n = 0, g IN groups | n + size(g.eps)) AS clean_total
WHERE clean_total >= 2
MATCH (f)<-[:AUTHORED]-(a:Agent)
MERGE (s:Session {id: $session})
CREATE (f2:Memory:Fact {id: f.id + '_v2', subject: f.subject, slot: f.slot, value: best,
                        tick: $tick, quarantined: false,
                        support_total: clean_total, support_clean: clean_total})
CREATE (f2)-[:SUPERSEDES]->(f), (a)-[:AUTHORED]->(f2), (f2)-[:RAN_IN]->(s)
WITH f, f2
MATCH (f)-[c:CONSOLIDATED_FROM]->(e:Episode) WHERE NOT e.quarantined
CREATE (f2)-[:CONSOLIDATED_FROM {claim: c.claim}]->(e)
RETURN f2.id, f2.value, count(e) AS support
"""

# Q5 fixpoint step: a blocked rework becomes ready when every blocker has a
# replacement. The harness runs this at the top of each Session 2 round until
# a whole round changes nothing.
PROMOTE_READY = """
MATCH (t:Task {state: 'blocked'})
OPTIONAL MATCH (t)-[:BLOCKED_BY]->(x:Memory) WHERE NOT (x)<-[:SUPERSEDES]-()
WITH t, count(x) AS open WHERE open = 0
SET t.state = 'ready'
RETURN count(t) AS promoted
"""

# Q6 per-agent start-up query. A fresh process asks: what of mine is
# quarantined and not yet replaced, is there a rework task for it, and what
# is it waiting on? Nothing else is loaded from Session 1.
STARTUP = """
MATCH (a:Agent {name: $me})-[:AUTHORED]->(m:Memory {quarantined: true})
WHERE NOT (m)<-[:SUPERSEDES]-()
OPTIONAL MATCH (t:Task)-[:REWORKS]->(m)
OPTIONAL MATCH (t)-[:BLOCKED_BY]->(x:Memory) WHERE NOT (x)<-[:SUPERSEDES]-()
RETURN m.id AS memory, m.healable AS healable, t.id AS task, t.state AS state,
       collect(x.id) AS waiting_on
ORDER BY m.tick
"""

# Q8 lease: claim a ready task, or take over an expired claim, atomically
# (FalkorDB serialises write queries per graph). 0 rows = someone holds it.
CLAIM = """
MATCH (t:Task {id: $task}), (a:Agent {name: $me})
OPTIONAL MATCH (t)-[c:CLAIMED_BY]->(holder)
WITH t, a, c, holder
WHERE t.state IN ['ready', 'claimed'] AND (c IS NULL OR c.lease_until < $now)
DELETE c
CREATE (t)-[:CLAIMED_BY {lease_until: $now + $lease, session: $session}]->(a)
SET t.state = 'claimed'
RETURN t.id, holder.name AS taken_over_from
"""

# Q8b finish a claimed rework: the replacement already exists (see
# loader.rework); mark done and drop the lease.
COMPLETE = """
MATCH (t:Task {id: $task})-[c:CLAIMED_BY]->(:Agent {name: $me})
SET t.state = 'done', t.done_tick = $tick
DELETE c
RETURN t.id
"""

# ---------------------------------------------------------------- audits (all must return 0)
AUDIT_NO_FORWARD_INFLUENCE = """
MATCH (m:Memory)-[:INFLUENCED_BY]->(x:Memory) WHERE x.tick >= m.tick RETURN count(*) AS bad
"""
AUDIT_CLEAN_NEVER_CITES_QUARANTINED = """
MATCH (m:Memory {quarantined: false})-[:INFLUENCED_BY|CONSOLIDATED_FROM]->(x:Memory {quarantined: true}) RETURN count(*) AS bad
"""
AUDIT_CLOSURE_IS_CLOSED = """
MATCH (x:Memory {quarantined: true})<-[:INFLUENCED_BY|CONSOLIDATED_FROM]-(m:Memory {quarantined: false}) RETURN count(*) AS bad
"""

# ---------------------------------------------------------------- read-only views for the UI
RED_WAVE = """
MATCH (m:Memory)
OPTIONAL MATCH (m)<-[:SUPERSEDES]-(r:Memory)
RETURN m.id AS id, labels(m)[1] AS kind, m.tick AS tick, m.quarantined AS red, count(r) > 0 AS superseded
ORDER BY m.tick
"""
COUNT_MEMORIES = "MATCH (m:Memory) RETURN count(m) AS n"
