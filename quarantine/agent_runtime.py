# quarantine/agent_runtime.py
"""Decision runtime and recovery status for Quarantine agents.

Provides deterministic decision rules (grounded in graph state) and
graph-derived recovery status for CLI, web, and MCP interfaces.
"""
from __future__ import annotations

import os
from typing import Any
from falkordb import Graph

from quarantine.queries import RESOLVED


def recovery_status(g: Graph) -> dict[str, Any]:
    """Inspects FalkorDB graph state and returns an auditable recovery status dictionary."""
    def _query(cypher: str, **params) -> list:
        return g.ro_query(cypher, params).result_set                  # read-only path, no write fallback

    # Total counts
    mem_rows = _query("MATCH (m:Memory) RETURN count(m)")
    mem_count = mem_rows[0][0] if mem_rows else 0

    quar_rows = _query("MATCH (m:Memory {quarantined: true}) RETURN count(m)")
    quarantined_count = quar_rows[0][0] if quar_rows else 0

    heal_rows = _query("MATCH (m:Memory)-[:SUPERSEDES]->() RETURN count(m)")
    healed_count = heal_rows[0][0] if heal_rows else 0

    # Tasks
    task_rows = _query("""
        MATCH (t:Task)
        OPTIONAL MATCH (t)-[:REWORKS]->(m:Memory)
        OPTIONAL MATCH (t)-[c:CLAIMED_BY]->(a:Agent)
        OPTIONAL MATCH (t)-[:BLOCKED_BY]->(b:Memory)
        WHERE t.state <> 'done' AND NOT %s
        RETURN t.id, t.state, m.id, a.name, c.lease_until, collect(DISTINCT b.id)
        ORDER BY t.id
    """ % (RESOLVED % "b"))
    tasks = []
    unfinished_tasks = 0
    for tid, state, mid, holder, lease, blockers in task_rows:
        tasks.append({
            "id": tid,
            "state": state,
            "reworks": mid,
            "claimed_by": holder,
            "lease_until": lease,
            "blocked_by": blockers,
        })
        if state != "done":
            unfinished_tasks += 1

    # Agents state
    agents_state = {}
    names = [r[0] for r in _query("MATCH (a:Agent)-[:AUTHORED]->(:Memory) RETURN DISTINCT a.name ORDER BY a.name")]
    for agent_name in names:                                            # whoever wrote memory, in any world
        memories = _query("""
            MATCH (a:Agent {name: $me})-[:AUTHORED]->(m:Memory)
            OPTIONAL MATCH (m)<-[:SUPERSEDES*1..]-(clean_rep:Memory {quarantined: false})   // the chain's clean head
            WITH m, count(clean_rep) > 0 AS resolved
            RETURN count(m) AS total,
                   count(CASE WHEN m.quarantined = true THEN 1 END) AS quarantined,
                   count(CASE WHEN m.quarantined = true AND resolved THEN 1 END) AS superseded
        """, me=agent_name)
        if memories:
            tot, quar, super_ = memories[0]
        else:
            tot, quar, super_ = 0, 0, 0
        agents_state[agent_name] = {
            "total_authored": tot,
            "quarantined": quar,
            "superseded": super_,
            "unresolved": quar - super_,
        }

    warnings = []
    if quarantined_count > 0 and unfinished_tasks > 0:
        warnings.append(f"{unfinished_tasks} rework task(s) remaining to reach fixpoint")
    # drift and unfinished repair: any of these means the graph is NOT in a state to call recovered
    provenance = "EXTRACTED_FROM|CONSOLIDATED_FROM|INFLUENCED_BY"
    checks = (
        (f"MATCH (:Doc {{flagged: true}})<-[:{provenance}*1..]-(m:Memory {{quarantined: false}}) RETURN count(DISTINCT m)",
         "memory(ies) reach a flagged doc but are not quarantined (torn write; run `quarantine session2`)"),
        (f"MATCH (m:Memory {{quarantined: true}}) WHERE NOT (m)-[:{provenance}*1..]->(:Doc {{flagged: true}}) RETURN count(m)",
         "quarantined memory(ies) reach no flagged doc (torn write; run `quarantine session2`)"),
        ("MATCH (m:Memory) WHERE (m:PlanStep OR m:Artifact) AND NOT (m)-[:INFLUENCED_BY]->() AND NOT (m)-[:SUPERSEDES]->() "
         "RETURN count(m)", "step(s) or artifact(s) have no read set (session 1 may have crashed; rerun it)"),
        ("MATCH (f:Fact {quarantined: true, healable: true}) WHERE NOT %s RETURN count(f)" % (RESOLVED % "f"),
         "healable fact(s) not healed yet"),
        ("MATCH (m:Memory {quarantined: false}) WHERE (m.needs_regeneration = true OR m.ungrounded = true) "
         "AND NOT (m)<-[:SUPERSEDES]-() RETURN count(m)",
         "replacement(s) are placeholders that an agent must regenerate (needs regeneration)"),
    )
    drift = _query("MATCH (s:Session {id: 's1'}) WHERE s.complete IS NULL OR s.complete <> true RETURN count(s)")[0][0]
    if drift:                                                           # killed mid-load: what is here is not the world
        warnings.append("session 1 did not finish (s1.complete missing; rerun `quarantine session1`)")
    for cypher, what in checks:
        n = _query(cypher)[0][0]
        if n:
            drift += n
            warnings.append(f"{n} {what}")

    is_complete = drift == 0 and ((quarantined_count == 0) or (len(tasks) > 0 and unfinished_tasks == 0))

    return {
        "mode": "scripted",
        "graph": getattr(g, "name", "quarantine"),
        "total_memories": mem_count,
        "quarantined_memories": quarantined_count,
        "healed_memories": healed_count,
        "agents": agents_state,
        "tasks": tasks,
        "complete": is_complete,
        "warnings": warnings,
    }


class AgentDecisionEngine:
    """Explains and executes agent decision policies based on graph state."""

    @staticmethod
    def research_consolidation_rule(claims: list[dict[str, Any]]) -> dict[str, Any]:
        """Research Agent consolidation rule:
        Given competing episode claims for a fact slot, evaluate strict plurality.
        Requires >= 2 agreeing clean sources to establish a consensus Fact.
        """
        counts: dict[str, int] = {}
        for c in claims:
            if not c.get("quarantined", False):
                val = c.get("claim")
                if val:
                    counts[val] = counts.get(val, 0) + 1

        if not counts:
            return {"decision": "unresolved", "value": None, "clean_votes": 0, "reason": "No clean sources"}

        sorted_claims = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        top_val, top_cnt = sorted_claims[0]

        # Must have at least 2 clean sources and strict plurality (no tie at top)
        if top_cnt < 2:
            return {
                "decision": "rejected",
                "value": None,
                "clean_votes": top_cnt,
                "reason": f"Insufficient clean evidence ({top_cnt} < 2 threshold)",
            }

        if len(sorted_claims) > 1 and sorted_claims[1][1] == top_cnt:
            return {
                "decision": "tie_halt",
                "value": None,
                "clean_votes": top_cnt,
                "reason": "Indeterminate consensus: clean evidence split evenly",
            }

        return {
            "decision": "consolidated",
            "value": top_val,
            "clean_votes": top_cnt,
            "reason": f"Strict plurality consensus ({top_cnt} agreeing clean episodes)",
        }

    @staticmethod
    def planner_readiness_rule(blocked_by: list[dict[str, Any]]) -> dict[str, Any]:
        """Planner Agent task claiming rule:
        A rework task is blocked if ANY dependency is quarantined without a clean SUPERSEDES head.
        """
        active_blockers = [
            b["id"] for b in blocked_by
            if b.get("quarantined") and not b.get("has_supersedes_head")
        ]
        if active_blockers:
            return {
                "state": "blocked",
                "action": "wait",
                "waiting_on": active_blockers,
                "reason": f"Upstream inputs are poisoned/unhealed: {active_blockers}",
            }
        return {
            "state": "ready",
            "action": "claim_and_execute",
            "waiting_on": [],
            "reason": "All causal blockers resolved or superseded with clean heads",
        }

    @staticmethod
    def coder_rework_guard(reads: list[dict[str, Any]]) -> dict[str, Any]:
        """Coder Agent write guard:
        Never emit an artifact that references missing or tainted memories.
        """
        tainted = [r["id"] for r in reads if r.get("quarantined", False)]
        missing = [r["id"] for r in reads if r.get("missing", False)]

        if tainted or missing:
            return {
                "allow_write": False,
                "violations": {"tainted": tainted, "missing": missing},
                "reason": "Harness security guard triggered: attempt to cite unreplaced tainted memory",
            }
        return {
            "allow_write": True,
            "violations": {},
            "reason": "Causal inputs verified clean and auditable",
        }
