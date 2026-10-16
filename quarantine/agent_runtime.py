# quarantine/agent_runtime.py
"""Decision runtime and recovery status for Quarantine agents.

Provides deterministic decision rules (grounded in graph state) and
graph-derived recovery status for CLI, web, and MCP interfaces.
"""
from __future__ import annotations

import os
from typing import Any
from falkordb import Graph


def recovery_status(g: Graph) -> dict[str, Any]:
    """Inspects FalkorDB graph state and returns an auditable recovery status dictionary."""
    def _query(cypher: str, **params) -> list:
        if hasattr(g, "ro_query"):
            return g.ro_query(cypher, params).result_set
        return g.query(cypher, params, read_only=True).result_set

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
        WHERE NOT (b)<-[:SUPERSEDES]-(:Memory {quarantined: false})
        RETURN t.id, t.state, m.id, a.name, c.lease_until, collect(DISTINCT b.id)
        ORDER BY t.id
    """)
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
    for agent_name in ("research", "planner", "coder"):
        memories = _query("""
            MATCH (a:Agent {name: $me})-[:AUTHORED]->(m:Memory)
            OPTIONAL MATCH (m)<-[:SUPERSEDES]-(clean_rep:Memory {quarantined: false})
            RETURN count(m) AS total,
                   count(CASE WHEN m.quarantined = true THEN 1 END) AS quarantined,
                   count(CASE WHEN clean_rep IS NOT NULL THEN 1 END) AS superseded
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

    is_complete = (quarantined_count == 0) or (len(tasks) > 0 and unfinished_tasks == 0)

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
