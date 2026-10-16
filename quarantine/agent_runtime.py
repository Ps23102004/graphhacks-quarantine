# quarantine/agent_runtime.py
"""Decision runtime and LLM execution hooks for Quarantine agents.

Provides deterministic decision rules (grounded in graph state) and
optional LLM-powered generation when API credentials are provided.
"""
from __future__ import annotations

import os
from typing import Any


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
                "reason": f"Insufficient clean evidence ({top_cnt} < 2 threshold)"
            }

        if len(sorted_claims) > 1 and sorted_claims[1][1] == top_cnt:
            return {
                "decision": "tie_halt",
                "value": None,
                "clean_votes": top_cnt,
                "reason": "Indeterminate consensus: clean evidence split evenly"
            }

        return {
            "decision": "consolidated",
            "value": top_val,
            "clean_votes": top_cnt,
            "reason": f"Strict plurality consensus ({top_cnt} agreeing clean episodes)"
        }

    @staticmethod
    def planner_readiness_rule(blocked_by: list[dict[str, Any]]) -> dict[str, Any]:
        """Planner Agent task claiming rule:
        A rework task is blocked if ANY dependency is quarantined without a SUPERSEDES head.
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
                "reason": f"Upstream inputs are poisoned/unhealed: {active_blockers}"
            }
        return {
            "state": "ready",
            "action": "claim_and_execute",
            "waiting_on": [],
            "reason": "All causal blockers resolved or superseded with clean heads"
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
                "reason": "Harness security guard triggered: attempt to cite unreplaced tainted memory"
            }
        return {
            "allow_write": True,
            "violations": {},
            "reason": "Causal inputs verified clean and auditable"
        }
