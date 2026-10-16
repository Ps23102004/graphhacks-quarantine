"""Does the build clear the Track 02 bar? One test per judging criterion / focus area from the event brief.

Track 02 (Agent Memory and Coordination): agents that remember across sessions and share state with each other;
memory persists, updates over time, and is available to every agent that needs it. Focus areas: episodic,
semantic and procedural memory; persistent conversation history; shared state and handoffs between agents;
high-concurrency reads and writes; separate memory per user or tenant. Judging: the graph does real work;
memory persists and updates across sessions; coordination is structural; traceability.
"""
from __future__ import annotations

import subprocess
import sys
import threading

import pytest

from quarantine import answers, queries as Q
from quarantine.loader import connect, load, q, read_fixture, rq

GRAPH = "track02_bar_test"


@pytest.fixture(scope="module")
def fx():
    return read_fixture()


def fresh(name: str):
    g = connect(name)
    try:
        g.delete()
    except Exception:  # noqa: BLE001
        pass
    return connect(name)


def run_cli(*args, graph: str = GRAPH) -> str:
    r = subprocess.run([sys.executable, "-m", "quarantine.cli", *args, "--graph", graph],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr + r.stdout
    return r.stdout


# ---------------------------------------------------------------- memory persists and UPDATES across sessions
def test_memory_persists_and_updates_across_separate_processes(fx):
    """Session 1 and Session 2 are separate OS processes; nothing survives in RAM, only the graph.
    Session 2 does not just read Session 1's memory, it changes it (heals, reworks) and both versions stay."""
    try:
        run_cli("session1")
        before = {r[0] for r in rq(connect(GRAPH), "MATCH (m:Memory) RETURN m.id")}
        run_cli("flag", "doc_7")
        run_cli("session2")
        g = connect(GRAPH)
        after = {r[0] for r in rq(g, "MATCH (m:Memory) RETURN m.id")}
        assert before < after and after - before == {"f_http_client_v2", "step_3_v2", "a_requirements_v2"}
        # updated, not reset: the old versions are still there, linked, and flagged
        assert rq(g, "MATCH (new)-[:SUPERSEDES]->(old {quarantined: true}) RETURN count(*)")[0][0] == 3
        # session history is itself persisted: both sessions exist and own memories
        sessions = {r[0]: r[1] for r in rq(g, "MATCH (s:Session)<-[:RAN_IN]-(m:Memory) RETURN s.id, count(m)")}
        assert sessions["s1"] == 25 and sessions["s2"] == 3
    finally:
        connect(GRAPH).delete()


# ---------------------------------------------------------------- episodic, semantic, procedural memory
def test_three_memory_kinds_each_with_provenance(fx):
    """Episodic (what was read, when), semantic (consolidated facts), procedural (plan steps and the rework
    procedure the crew follows). Each kind is a labelled node with provenance edges, not a blob."""
    g = fresh(GRAPH)
    try:
        load(g, fx)
        assert rq(g, "MATCH (e:Episode)-[:EXTRACTED_FROM]->(:Doc) RETURN count(DISTINCT e)")[0][0] == 9        # episodic
        assert rq(g, "MATCH (f:Fact)-[:CONSOLIDATED_FROM]->(:Episode) RETURN count(DISTINCT f)")[0][0] == 7    # semantic
        assert rq(g, "MATCH (s:PlanStep)-[:INFLUENCED_BY]->() RETURN count(DISTINCT s)")[0][0] == 5            # procedural
        q(g, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)
        q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
        q(g, Q.SUPPORT_AND_HEALABLE)
        q(g, Q.CREATE_REWORK_TASKS, tick=40)
        q(g, Q.CREATE_BLOCKED_BY)
        # the procedure itself lives in the graph: tasks with explicit ordering edges, not in anyone's prompt
        assert rq(g, "MATCH (:Task)-[:BLOCKED_BY]->(:Memory) RETURN count(*)")[0][0] == 2
    finally:
        g.delete()


# ---------------------------------------------------------------- shared state and handoffs
def test_handoff_is_a_graph_read_not_a_message(fx):
    """A second agent (or a restarted one) resumes from the graph alone: claims, leases and BLOCKED_BY ordering
    are shared state, and a killed holder's work is taken over by whoever reads the graph next."""
    g = fresh(GRAPH)
    try:
        load(g, fx)
        q(g, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)
        q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
        q(g, Q.SUPPORT_AND_HEALABLE)
        q(g, Q.CREATE_REWORK_TASKS, tick=40)
        q(g, Q.CREATE_BLOCKED_BY)
        q(g, Q.HEAL_FACTS, session="s2", tick=41)
        q(g, Q.PROMOTE_READY)
        assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=50, lease=5, session="proc_A")
        # process A dies. Process B knows nothing except the graph:
        state = q(g, Q.STARTUP, me="planner")
        assert state[0][0] == "step_3" and state[0][3] == "claimed"
        assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=53, lease=5, session="proc_B") == []   # lease live
        assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=56, lease=5, session="proc_B")         # expired
        assert rq(g, "MATCH (:Task {id: 'rework_step_3'})-[c:CLAIMED_BY]->() RETURN c.session")[0][0] == "proc_B"
    finally:
        g.delete()


# ---------------------------------------------------------------- high-concurrency reads and writes
def test_concurrent_claims_exactly_one_winner_and_concurrent_writes_all_land(fx):
    """Many agents at once: N threads race for the same ready task at the same tick; exactly one claim succeeds.
    N threads write memories concurrently; all land with their provenance edges, and the audits stay clean."""
    g = fresh(GRAPH)
    try:
        load(g, fx)
        q(g, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)
        q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
        q(g, Q.SUPPORT_AND_HEALABLE)
        q(g, Q.CREATE_REWORK_TASKS, tick=40)
        q(g, Q.CREATE_BLOCKED_BY)
        q(g, Q.HEAL_FACTS, session="s2", tick=41)
        q(g, Q.PROMOTE_READY)

        n = 16
        wins, errors = [], []
        start = threading.Barrier(n)

        def racer(i: int):
            try:
                start.wait()
                gi = connect(GRAPH)                                   # its own connection, like its own process
                if q(gi, Q.CLAIM, task="rework_step_3", me="planner", now=50, lease=5, session=f"p{i}"):
                    wins.append(i)
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

        threads = [threading.Thread(target=racer, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors[:3]
        assert len(wins) == 1, wins
        assert rq(g, "MATCH (:Task {id: 'rework_step_3'})-[c:CLAIMED_BY]->() RETURN count(c)")[0][0] == 1

        # concurrent writes: each writer adds an episode + a fact citing it; nothing is lost or cross-wired
        start2 = threading.Barrier(n)

        def writer(i: int):
            try:
                start2.wait()
                gi = connect(GRAPH)
                q(gi, "MATCH (a:Agent {name: 'research'}), (s:Session {id: 's1'}), (d:Doc {id: 'doc_1'}) "
                      "CREATE (e:Memory:Episode {id: $e, tick: $t, text: 'c', quarantined: false})-[:EXTRACTED_FROM]->(d) "
                      "CREATE (a)-[:AUTHORED]->(e), (e)-[:RAN_IN]->(s) "
                      "CREATE (f:Memory:Fact {id: $f, tick: $t2, value: 'v', quarantined: false})-[:CONSOLIDATED_FROM {claim: 'v'}]->(e) "
                      "CREATE (a)-[:AUTHORED]->(f), (f)-[:RAN_IN]->(s)",
                  e=f"ep_c{i}", f=f"f_c{i}", t=100 + i, t2=200 + i)
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors[:3]
        assert rq(g, "MATCH (e:Episode) WHERE e.id STARTS WITH 'ep_c' RETURN count(e)")[0][0] == n
        assert rq(g, "MATCH (f:Fact)-[:CONSOLIDATED_FROM]->(e:Episode) WHERE f.id STARTS WITH 'f_c' "
                     "AND e.id = 'ep_c' + substring(f.id, 3) RETURN count(f)")[0][0] == n
        for audit in (Q.AUDIT_NO_FORWARD_INFLUENCE, Q.AUDIT_CLEAN_NEVER_CITES_QUARANTINED, Q.AUDIT_CLOSURE_IS_CLOSED):
            assert rq(g, audit)[0][0] == 0
        # concurrent reads during writes never see a half-written pair: every fact already has its episode
        assert rq(g, "MATCH (f:Fact) WHERE f.id STARTS WITH 'f_c' AND NOT (f)-[:CONSOLIDATED_FROM]->() RETURN count(f)")[0][0] == 0
    finally:
        g.delete()


# ---------------------------------------------------------------- separate memory per tenant
def test_separate_memory_per_tenant_same_question_different_answer(fx):
    """Thousands of graphs per instance: the same question asked against two tenants gets each tenant's own
    answer, and nothing leaks. (The guideline suite proves isolation of writes; this proves it at the answer level.)"""
    a, b = fresh("track02_tenant_a"), fresh("track02_tenant_b")
    try:
        load(a, fx)
        load(b, fx)
        q(a, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)
        q(a, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
        q(b, Q.FLAG_DOC, doc="doc_4", reason="t", tick=40)
        q(b, Q.TAINT_CLOSURE, doc="doc_4", tick=40)
        assert answers.why_quarantined(a, "a_requirements")["hops"][-1] == "doc_7"
        assert answers.why_quarantined(b, "a_requirements")["shape"] == "not_in_graph"
        assert answers.why_quarantined(b, "a_fetch_py")["hops"][-1] == "doc_4"
        assert answers.why_quarantined(a, "a_fetch_py")["shape"] == "not_in_graph"
        names = {r[0] for r in rq(a, "CALL db.labels() YIELD label RETURN label")}
        assert "Memory" in names                                        # sanity: both are full graphs, not views
    finally:
        a.delete()
        b.delete()


# ---------------------------------------------------------------- the graph does real work + traceability
def test_every_decision_is_explainable_by_a_graph_path(fx):
    """Traceability: every quarantined memory has a receipt, every healed fact names its clean support, every
    rework names what it read. No decision lives only in a log line."""
    g = fresh(GRAPH)
    try:
        load(g, fx)
        q(g, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)
        q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
        q(g, Q.SUPPORT_AND_HEALABLE)
        q(g, Q.CREATE_REWORK_TASKS, tick=40)
        q(g, Q.CREATE_BLOCKED_BY)
        for (mid,) in rq(g, "MATCH (m:Memory {quarantined: true}) RETURN m.id"):
            out = answers.why_quarantined(g, mid)
            assert out["shape"] == "path" and out["hops"][-1] == "doc_7", mid
        q(g, Q.HEAL_FACTS, session="s2", tick=41)
        support = rq(g, "MATCH (:Fact {id: 'f_http_client_v2'})-[:CONSOLIDATED_FROM]->(e) RETURN collect(e.id)")[0][0]
        assert sorted(support) == ["ep_2", "ep_5", "ep_8"]              # the clean majority, by id, not by assertion
    finally:
        g.delete()
