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
# three edge types, any depth (the graph is a DAG: reads only point backwards in time). Returns the "precise" count.
TAINT_CLOSURE = """
MATCH (d:Doc {id: $doc})<-[:EXTRACTED_FROM|CONSOLIDATED_FROM|INFLUENCED_BY*1..]-(m:Memory)
SET m.quarantined = true, m.quarantine_tick = $tick
RETURN count(DISTINCT m) AS precise, collect(DISTINCT m.id) AS ids
"""

# Q2 baseline: "reset the compromised agent". Every memory authored by any agent
# that authored anything in the closure.
NAIVE_PER_AGENT = """
MATCH (d:Doc {id: $doc})<-[:EXTRACTED_FROM|CONSOLIDATED_FROM|INFLUENCED_BY*1..]-(:Memory)<-[:AUTHORED]-(a:Agent)
WITH DISTINCT a
MATCH (a)-[:AUTHORED]->(all:Memory) WHERE NOT (all)-[:SUPERSEDES]->()
RETURN count(DISTINCT all) AS naive, collect(DISTINCT a.name) AS agents_wiped
"""

# Q2b baseline: "invalidate everything written after the bad doc came in"
# (what a time-based memory store can do). Kills clean work too.
NAIVE_TIME_BASED = """
MATCH (d:Doc {id: $doc})<-[:EXTRACTED_FROM]-(e:Episode)
WITH min(e.tick) AS t0
MATCH (m:Memory) WHERE m.tick >= t0 AND NOT (m)-[:SUPERSEDES]->()
RETURN count(m) AS naive_time, max(t0) AS t0
"""

# Q3 hero: the receipt. Why is THIS artifact red? FalkorDB only allows
# shortestPath in WITH/RETURN (spike S2a), never in MATCH.
RECEIPT = """
MATCH (a:Memory {id: $from}), (d:Doc {id: $doc})
WITH shortestPath((a)-[:INFLUENCED_BY|CONSOLIDATED_FROM|EXTRACTED_FROM*]->(d)) AS p
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
OPTIONAL MATCH (m)-[c:CONSOLIDATED_FROM]->(e:Episode) WHERE NOT e.quarantined
WITH m, c.claim AS claim, count(DISTINCT e) AS n ORDER BY n DESC
WITH m, collect(n) AS ns
WITH m, reduce(t = 0, x IN ns | t + x) AS clean, head(ns) AS best,
     CASE WHEN size(ns) > 1 THEN ns[1] ELSE 0 END AS second
SET m.support_clean = CASE WHEN m:Fact THEN clean ELSE null END,
    m.healable = CASE WHEN NOT m.quarantined THEN null
                      WHEN m:Episode THEN false
                      WHEN m:Fact THEN best >= 2 AND best > second
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
OPTIONAL MATCH (t_old:Task {kind: 'rework'})-[b:BLOCKED_BY]->(x_old:Memory)
WHERE x_old.quarantined <> true OR x_old.healable <> true
DELETE b
WITH count(*) AS dummy
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
WITH f, c.claim AS claim, collect(DISTINCT e) AS eps ORDER BY size(eps) DESC, claim
WITH f, collect({claim: claim, eps: eps}) AS groups
WITH f, groups[0].claim AS best, groups[0].eps AS agree,
     CASE WHEN size(groups) > 1 THEN size(groups[1].eps) ELSE 0 END AS second_cnt
WHERE size(agree) >= 2 AND size(agree) > second_cnt
MATCH (f)<-[:AUTHORED]-(a:Agent)
MERGE (s:Session {id: $session})
CREATE (f2:Memory:Fact {id: f.id + '_v2', subject: f.subject, slot: f.slot, value: best,
                        tick: $tick, quarantined: false,
                        support_total: size(agree), support_clean: size(agree)})
CREATE (f2)-[:SUPERSEDES]->(f), (a)-[:AUTHORED]->(f2), (f2)-[:RAN_IN]->(s)
WITH f2, best, agree
UNWIND agree AS e
CREATE (f2)-[:CONSOLIDATED_FROM {claim: best}]->(e)
RETURN f2.id, f2.value, count(e) AS support
"""

# Q5 fixpoint step: a blocked rework becomes ready when every blocker has a
# replacement. The harness runs this at the top of each Session 2 round until
# a whole round changes nothing.
PROMOTE_READY = """
MATCH (t:Task {state: 'blocked'})
OPTIONAL MATCH (t)-[:BLOCKED_BY]->(x:Memory) WHERE NOT (x)<-[:SUPERSEDES]-(:Memory {quarantined: false})
WITH t, count(x) AS open WHERE open = 0
SET t.state = 'ready'
RETURN count(t) AS promoted
"""

# Q6 per-agent start-up query. A fresh process asks: what of mine is
# quarantined and not yet replaced, is there a rework task for it, and what
# is it waiting on? Unfinished tasks (ready or claimed) are returned so a restarted
# worker can resume work.
STARTUP = """
MATCH (a:Agent {name: $me})-[:AUTHORED]->(m:Memory {quarantined: true})
OPTIONAL MATCH (t:Task)-[:REWORKS]->(m)
OPTIONAL MATCH (m)<-[:SUPERSEDES]-(clean_rep:Memory {quarantined: false})
WITH a, m, t, clean_rep
WHERE clean_rep IS NULL OR (t IS NOT NULL AND t.state IN ['ready', 'claimed'])
OPTIONAL MATCH (t)-[:BLOCKED_BY]->(x:Memory) WHERE NOT (x)<-[:SUPERSEDES]-(:Memory {quarantined: false})
RETURN m.id AS memory, m.healable AS healable, t.id AS task, t.state AS state,
       collect(x.id) AS waiting_on
ORDER BY m.tick
"""

# Q8 lease: claim a ready task, or take over an expired claim, atomically
# (FalkorDB serialises write queries per graph). 0 rows = someone holds it.
CLAIM = """
MATCH (t:Task {id: $task})-[:REWORKS]->(:Memory)<-[:AUTHORED]-(a:Agent {name: $me})
OPTIONAL MATCH (t)-[c:CLAIMED_BY]->(holder)
WITH t, a, c, holder
WHERE t.state IN ['ready', 'claimed'] AND (c IS NULL OR c.lease_until < $now)
DELETE c
CREATE (t)-[:CLAIMED_BY {lease_until: $now + $lease, session: $session}]->(a)
SET t.state = 'claimed'
RETURN t.id, holder.name AS taken_over_from
"""

# Q8b finish a claimed rework: the clean replacement already exists (see
# loader.rework); mark done and drop the lease.
COMPLETE = """
MATCH (t:Task {id: $task})-[:REWORKS]->(:Memory)<-[:SUPERSEDES]-(rep:Memory {quarantined: false})
MATCH (t)-[c:CLAIMED_BY {session: $session}]->(:Agent {name: $me})
WHERE c.lease_until >= $now
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
OPTIONAL MATCH (m)-[:SUPERSEDES]->(old:Memory)
OPTIONAL MATCH (m)<-[:AUTHORED]-(a:Agent)
RETURN m.id, labels(m)[1], m.tick, m.quarantined, a.name, m.text, old.id, m.value, m.path
ORDER BY m.tick
"""
COUNT_MEMORIES = "MATCH (m:Memory) RETURN count(m)"
