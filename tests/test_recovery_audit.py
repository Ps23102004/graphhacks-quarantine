# tests/test_recovery_audit.py
"""Comprehensive verification of recovery mechanisms, lease fencing, atomic writes,
fixture validation, and graph-derived recovery status.
"""
from __future__ import annotations

import json
import subprocess
import sys
import pytest

from quarantine import queries as Q
from quarantine.agent_runtime import recovery_status
from quarantine.loader import connect, load, q, read_fixture, rework, validate_fixture

GRAPH = "quarantine_recovery_audit_test"


@pytest.fixture
def g():
    graph = connect(GRAPH)
    try:
        graph.delete()
    except Exception:
        pass
    graph = connect(GRAPH)
    yield graph
    try:
        graph.delete()
    except Exception:
        pass


def test_fixture_validation_guards():
    fx = read_fixture()
    validate_fixture(fx)

    # Missing section
    with pytest.raises(ValueError, match="missing required dictionary section"):
        validate_fixture({"docs": {}})

    # Unknown doc reference
    broken_fx = json.loads(json.dumps(fx))
    broken_fx["episodes"]["ep_1"]["doc"] = "doc_unknown"
    with pytest.raises(ValueError, match="references unknown doc"):
        validate_fixture(broken_fx)

    # Unknown read reference
    broken_fx2 = json.loads(json.dumps(fx))
    broken_fx2["steps"]["step_1"]["reads"].append("memory_phantom")
    with pytest.raises(ValueError, match="references unknown memory"):
        validate_fixture(broken_fx2)

    # Temporal forward reference violation
    broken_fx3 = json.loads(json.dumps(fx))
    broken_fx3["steps"]["step_1"]["tick"] = 5
    broken_fx3["steps"]["step_1"]["reads"] = ["f_goal"]  # f_goal has tick 10
    with pytest.raises(ValueError, match="Temporal violation"):
        validate_fixture(broken_fx3)


def test_rework_author_and_lease_fencing(g):
    fx = read_fixture()
    load(g, fx)
    q(g, Q.FLAG_DOC, doc="doc_7", reason="test", tick=40)
    q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
    q(g, Q.SUPPORT_AND_HEALABLE)
    q(g, Q.CREATE_REWORK_TASKS, tick=40)
    q(g, Q.CREATE_BLOCKED_BY)
    q(g, Q.HEAL_FACTS, session="s2", tick=41)
    q(g, Q.PROMOTE_READY)

    # 1. Non-author cannot rework (e.g., coder attempting to rework planner's step_3)
    spec = fx["rework"]["step_3"]
    with pytest.raises(ValueError, match="Unauthorized rework: agent 'coder' is not the author"):
        rework(g, "step_3", "coder", spec["text"], spec["reads"], 42, "s2")

    # 2. Claim task by planner in session s2
    assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=42, lease=5, session="s2")

    # 3. Zombie session s1 cannot write while s2 holds the lease
    with pytest.raises(ValueError, match="Zombie or unauthorized write"):
        rework(g, "step_3", "planner", spec["text"], spec["reads"], 43, "s1")

    # 4. Expired lease prevents write without renewal
    with pytest.raises(ValueError, match="Lease expired"):
        rework(g, "step_3", "planner", spec["text"], spec["reads"], 55, "s2")

    # 5. Valid holder writes atomically and creates full provenance
    new_id = rework(g, "step_3", "planner", spec["text"], spec["reads"], 43, "s2")
    assert new_id == "step_3_v2"
    reads = set(r[0] for r in q(g, "MATCH (:Memory {id: 'step_3_v2'})-[:INFLUENCED_BY]->(x) RETURN x.id"))
    assert reads == set(spec["reads"])

    # 6. Idempotent retry returns existing id without duplicating nodes or edges
    retry_id = rework(g, "step_3", "planner", spec["text"], spec["reads"], 44, "s2")
    assert retry_id == "step_3_v2"
    assert q(g, "MATCH (m:Memory {id: 'step_3_v2'}) RETURN count(m)")[0][0] == 1


def test_reconcile_blocked_by_removes_dead_blockers(g):
    """When a second advisory causes a previously healable fact to become dead,
    CREATE_BLOCKED_BY reconciles and removes obsolete BLOCKED_BY edges.
    """
    fx = read_fixture()
    load(g, fx)

    # Flag doc_7 first: f_http_client is healable (3 clean sources), step_3 is blocked by f_http_client
    q(g, Q.FLAG_DOC, doc="doc_7", reason="typo", tick=40)
    q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
    q(g, Q.SUPPORT_AND_HEALABLE)
    q(g, Q.CREATE_REWORK_TASKS, tick=40)
    q(g, Q.CREATE_BLOCKED_BY)

    blockers1 = {r[0]: r[1] for r in q(g, "MATCH (t:Task)-[:BLOCKED_BY]->(b) RETURN t.id, collect(b.id)")}
    assert "f_http_client" in blockers1.get("rework_step_3", [])

    # Now flag doc_2, doc_5, and doc_8 (the remaining clean episodes for f_http_client)
    # Now f_http_client has 0 clean sources -> healable becomes false (dead)
    for d in ("doc_2", "doc_5", "doc_8"):
        q(g, Q.FLAG_DOC, doc=d, reason="batch", tick=45)
        q(g, Q.TAINT_CLOSURE, doc=d, tick=45)

    q(g, Q.SUPPORT_AND_HEALABLE)
    q(g, Q.CREATE_BLOCKED_BY)

    # Reconciled: f_http_client is dead, so it should no longer block rework_step_3
    blockers2 = {r[0]: r[1] for r in q(g, "MATCH (t:Task)-[:BLOCKED_BY]->(b) RETURN t.id, collect(b.id)")}
    assert "f_http_client" not in blockers2.get("rework_step_3", [])


def test_recovery_status_and_cli_status(g):
    fx = read_fixture()
    load(g, fx)

    # Initially complete (no quarantine)
    st1 = recovery_status(g)
    assert st1["mode"] == "scripted"
    assert st1["total_memories"] == 25
    assert st1["quarantined_memories"] == 0
    assert st1["complete"] is True
    assert st1["warnings"] == []

    # Flag doc_7
    q(g, Q.FLAG_DOC, doc="doc_7", reason="test", tick=40)
    q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
    q(g, Q.SUPPORT_AND_HEALABLE)
    q(g, Q.CREATE_REWORK_TASKS, tick=40)
    q(g, Q.CREATE_BLOCKED_BY)

    st2 = recovery_status(g)
    assert st2["quarantined_memories"] == 6
    assert st2["complete"] is False
    assert len(st2["tasks"]) == 2
    assert len(st2["warnings"]) > 0

    # Test CLI quarantine status command
    res = subprocess.run([sys.executable, "-m", "quarantine.cli", "status", "--graph", GRAPH],
                         capture_output=True, text=True, check=True)
    parsed = json.loads(res.stdout)
    assert parsed["quarantined_memories"] == 6
    assert parsed["complete"] is False


def test_session1_cli_negative_slow_rejected():
    res = subprocess.run([sys.executable, "-m", "quarantine.cli", "session1", "--slow", "-1"],
                         capture_output=True, text=True)
    assert res.returncode != 0
    assert "non-negative finite number" in res.stderr or "non-negative finite number" in res.stdout


def test_verify_queries_spike_executes_cleanly():
    from pathlib import Path
    repo_root = Path(__file__).resolve().parent.parent
    res = subprocess.run([sys.executable, str(repo_root / "spikes" / "verify_queries.py")],
                         cwd=str(repo_root), capture_output=True, text=True, check=True)
    assert "=== AUDIT_NO_FORWARD_INFLUENCE" in res.stdout
    assert "AUDIT_CLEAN_NEVER_CITES_QUARANTINED" in res.stdout
    assert "AUDIT_CLOSURE_IS_CLOSED" in res.stdout
    assert "COMPLETE" in res.stdout
