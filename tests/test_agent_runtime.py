# tests/test_agent_runtime.py
"""Tests for agent decision logic, causal guards, and multi-scenario edge cases."""
from __future__ import annotations

import pytest
from quarantine.agent_runtime import AgentDecisionEngine


def test_research_consolidation_plurality():
    # Scenario 1: Clean majority (3 votes for 'requests', 1 tainted vote ignored)
    claims = [
        {"claim": "requests", "quarantined": False},
        {"claim": "requests", "quarantined": False},
        {"claim": "requests", "quarantined": False},
        {"claim": "reqeusts", "quarantined": True},  # injected
    ]
    res = AgentDecisionEngine.research_consolidation_rule(claims)
    assert res["decision"] == "consolidated"
    assert res["value"] == "requests"
    assert res["clean_votes"] == 3


def test_research_consolidation_insufficient_support():
    # Scenario 2: Single source (below >=2 threshold)
    claims = [
        {"claim": "httpx", "quarantined": False},
        {"claim": "bad_lib", "quarantined": True},
    ]
    res = AgentDecisionEngine.research_consolidation_rule(claims)
    assert res["decision"] == "rejected"
    assert res["value"] is None
    assert "Insufficient clean evidence" in res["reason"]


def test_research_consolidation_tie_halts_consensus():
    # Scenario 3: 2 clean vs 2 clean -> Tie should not guess alphabetically
    claims = [
        {"claim": "urllib3", "quarantined": False},
        {"claim": "urllib3", "quarantined": False},
        {"claim": "requests", "quarantined": False},
        {"claim": "requests", "quarantined": False},
    ]
    res = AgentDecisionEngine.research_consolidation_rule(claims)
    assert res["decision"] == "tie_halt"
    assert res["value"] is None
    assert "split evenly" in res["reason"]


def test_planner_readiness_gated_by_taint():
    # Scenario 4: Blocked task waiting on unhealed fact
    blockers = [
        {"id": "f_http_client", "quarantined": True, "has_supersedes_head": False},
        {"id": "f_deps", "quarantined": False, "has_supersedes_head": False},
    ]
    decision = AgentDecisionEngine.planner_readiness_rule(blockers)
    assert decision["state"] == "blocked"
    assert decision["waiting_on"] == ["f_http_client"]

    # Scenario 5: Unblocks once superseded
    blockers_healed = [
        {"id": "f_http_client", "quarantined": True, "has_supersedes_head": True},
        {"id": "f_deps", "quarantined": False, "has_supersedes_head": False},
    ]
    decision_healed = AgentDecisionEngine.planner_readiness_rule(blockers_healed)
    assert decision_healed["state"] == "ready"
    assert decision_healed["action"] == "claim_and_execute"


def test_coder_rework_guard_enforcement():
    # Scenario 6: Attempting to cite tainted memory directly fails
    reads_tainted = [
        {"id": "f_http_client", "quarantined": True},
        {"id": "f_deps", "quarantined": False},
    ]
    guard = AgentDecisionEngine.coder_rework_guard(reads_tainted)
    assert guard["allow_write"] is False
    assert "f_http_client" in guard["violations"]["tainted"]

    # Scenario 7: All clean inputs succeeds
    reads_clean = [
        {"id": "f_http_client_v2", "quarantined": False},
        {"id": "f_deps", "quarantined": False},
    ]
    guard_clean = AgentDecisionEngine.coder_rework_guard(reads_clean)
    assert guard_clean["allow_write"] is True
