"""Every number the demo says out loud, asserted against a local FalkorDB.

    docker run -d --name quarantine-falkordb -p 6379:6379 -p 3000:3000 \
      falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
    uv run pytest -q
"""
from __future__ import annotations

import pytest

from quarantine import queries as Q
from quarantine.loader import connect, load, q, read_fixture, rework

GRAPH = "quarantine_test"


@pytest.fixture(scope="module")
def fx() -> dict:
    return read_fixture()


@pytest.fixture
def g(fx):
    g = connect(GRAPH)
    try:
        g.delete()
    except Exception:  # noqa: BLE001  (graph did not exist)
        pass
    g = connect(GRAPH)
    load(g, fx)
    yield g
    g.delete()


def ids(rows):
    return {r[0] for r in rows}


def read_set(g, mid):
    return ids(q(g, "MATCH (m:Memory {id: $id})-[:INFLUENCED_BY]->(x) RETURN x.id", id=mid))


def quarantined(g):
    return ids(q(g, "MATCH (m:Memory {quarantined: true}) RETURN m.id"))


def audits_clean(g):
    return [q(g, a)[0][0] for a in (Q.AUDIT_NO_FORWARD_INFLUENCE,
                                    Q.AUDIT_CLEAN_NEVER_CITES_QUARANTINED,
                                    Q.AUDIT_CLOSURE_IS_CLOSED)]


def open_session2(g, fx) -> int:
    """The advisory lands: flag, closure, support counts, rework tasks. Returns the precise count."""
    flag = fx["flag"]
    q(g, Q.FLAG_DOC, doc=flag["doc"], reason=flag["reason"], tick=flag["tick"])
    precise, _ = q(g, Q.TAINT_CLOSURE, doc=flag["doc"], tick=flag["tick"])[0]
    q(g, Q.SUPPORT_AND_HEALABLE)
    q(g, Q.CREATE_REWORK_TASKS, tick=flag["tick"])
    q(g, Q.CREATE_BLOCKED_BY)
    return precise


def session2_rounds(g, fx, tick: int = 41, lease: int = 5) -> list[int]:
    """Harness scheduler for Session 2: each round promotes ready tasks, then every
    agent (fresh process, start-up query only) does the work that is ready for it.
    Stops when a whole round changes nothing. Returns changes per round."""
    changes = []
    while True:
        n = q(g, Q.PROMOTE_READY)[0][0]
        n += len(q(g, Q.HEAL_FACTS, session="s2", tick=tick))          # research/consolidator
        tick += 1
        for agent in ("planner", "coder"):
            for memory, _healable, task, state, _waiting in q(g, Q.STARTUP, me=agent):
                if state != "ready":
                    continue
                spec = fx["rework"][memory]
                assert q(g, Q.CLAIM, task=task, me=agent, now=tick, lease=lease, session="s2")
                rework(g, memory, agent, spec["text"], spec["reads"], tick, "s2")
                q(g, Q.COMPLETE, task=task, me=agent, tick=tick, now=tick, session="s2")
                tick += 1
                n += 1
        changes.append(n)
        if n == 0:
            return changes


# ---------------------------------------------------------------- Session 1
def test_fixture_loads_and_is_consistent(g, fx):
    assert q(g, Q.COUNT_MEMORIES)[0][0] == fx["expected"]["total_memories"]
    assert quarantined(g) == set()
    assert audits_clean(g) == [0, 0, 0]


# ---------------------------------------------------------------- Session 2: closure
def test_closure_is_precise_and_baselines_are_not(g, fx):
    ex, doc = fx["expected"], fx["flag"]["doc"]
    precise = open_session2(g, fx)
    assert precise == ex["precise"] == len(ex["closure_ids"])
    assert quarantined(g) == set(ex["closure_ids"])

    naive, agents = q(g, Q.NAIVE_PER_AGENT, doc=doc)[0]
    assert naive == ex["naive_per_agent"] and set(agents) == {"research", "planner", "coder"}
    naive_time, t0 = q(g, Q.NAIVE_TIME_BASED, doc=doc)[0]
    assert naive_time == ex["naive_time_based"] and t0 == fx["episodes"]["ep_7a"]["tick"]
    assert precise < naive_time < naive

    # writes before the tainted read, and clean writes after it, both stay green
    for mid in ex["green_before_tainted_read"] + ex["green_after_tainted_read"]:
        assert mid not in quarantined(g), mid
    assert audits_clean(g) == [0, 0, 0]


def test_receipt_is_a_shortest_path_through_the_planner(g, fx):
    ex = fx["expected"]["receipt"]
    open_session2(g, fx)
    hops, length, via = q(g, Q.RECEIPT, **{"from": ex["from"], "doc": ex["to"]})[0]
    assert length == ex["hops"] and hops[0] == ex["from"] and hops[-1] == ex["to"]
    assert hops[1] in ex["via"]                                       # the Coder never read doc_7 itself
    # two shortest paths tie (via the package fact or via the version pin); both are valid receipts
    assert (hops[2], hops[3]) in {("f_http_client", "ep_7a"), ("f_http_pin", "ep_7b")}
    assert set(hops[1:-1]) <= set(fx["expected"]["closure_ids"])        # every hop on the receipt is red
    assert via == ["INFLUENCED_BY", "INFLUENCED_BY", "CONSOLIDATED_FROM", "EXTRACTED_FROM"]

    hops2, length2 = q(g, Q.RECEIPT_SPPATHS, **{"from": ex["from"], "doc": ex["to"]})[0]
    assert length2 == ex["hops"] and hops2[0] == hops[0] and hops2[-1] == hops[-1]

    # a clean artifact has no receipt at all (null path: nodes() -> [], length() -> null)
    assert q(g, Q.RECEIPT, **{"from": "a_fetch_py", "doc": ex["to"]})[0][:2] == [[], None]


def test_support_counts_and_rework_ordering(g, fx):
    ex = fx["expected"]
    open_session2(g, fx)
    rows = {r[0]: (r[1], r[2]) for r in q(g, Q.SUPPORT_AND_HEALABLE)}
    assert rows["f_http_client"] == (ex["heal"]["f_http_client"]["support_clean"], True)
    assert rows["f_http_pin"] == (0, False)
    assert rows["f_http_usage"] == (2, None)                            # clean facts carry counts but no verdict
    for mid in ex["dead"]:
        assert rows[mid][1] is False
    blocked = {r[0]: set(r[1]) for r in q(g, Q.CREATE_BLOCKED_BY)}
    assert blocked == {k: set(v) for k, v in ex["rework_tasks"].items()}


# ---------------------------------------------------------------- Session 2: heal + rework fixpoint
def test_session2_heals_then_reworks_in_dependency_order(g, fx):
    ex = fx["expected"]
    open_session2(g, fx)
    assert session2_rounds(g, fx) == ex["session2_round_changes"]

    value, support = q(g, "MATCH (f:Fact {id: 'f_http_client_v2'})-[:CONSOLIDATED_FROM]->(e) "
                          "RETURN f.value, count(e)")[0]
    assert value == ex["heal"]["f_http_client"]["value"] and support == ex["heal"]["f_http_client"]["support_clean"]
    assert q(g, "MATCH (n:Memory {id: 'f_http_client_v2'})-[:SUPERSEDES]->(o) RETURN o.id")[0][0] == "f_http_client"

    for mid in ex["dead"]:                                              # never healed, still red, kept as history
        assert q(g, "MATCH (m:Memory {id: $id}) OPTIONAL MATCH (m)<-[:SUPERSEDES]-(r) "
                    "RETURN m.quarantined, count(r)", id=mid)[0] == [True, 0]

    assert q(g, Q.COUNT_MEMORIES)[0][0] == ex["memories_after_session2"]
    assert quarantined(g) == set(ex["closure_ids"])                     # the poisoned lineage stays flagged
    assert ids(q(g, "MATCH (t:Task) WHERE t.state <> 'done' RETURN t.id")) == set()
    assert read_set(g, "step_3_v2") == set(fx["rework"]["step_3"]["reads"])
    assert read_set(g, "a_requirements_v2") == set(fx["rework"]["a_requirements"]["reads"])
    assert audits_clean(g) == [0, 0, 0]
    for agent in ("research", "planner", "coder"):                      # start-up queries come back empty
        assert [r for r in q(g, Q.STARTUP, me=agent) if r[1] is not False] == []


def test_startup_query_is_per_agent(g, fx):
    open_session2(g, fx)
    research = {r[0]: r[1:] for r in q(g, Q.STARTUP, me="research")}
    assert set(research) == {"ep_7a", "ep_7b", "f_http_client", "f_http_pin"}
    assert research["f_http_client"][0] is True and research["f_http_pin"][0] is False
    assert q(g, Q.STARTUP, me="planner") == [["step_3", True, "rework_step_3", "blocked", ["f_http_client"]]]
    assert q(g, Q.STARTUP, me="coder") == [["a_requirements", True, "rework_a_requirements", "blocked", ["step_3"]]]

    q(g, Q.HEAL_FACTS, session="s2", tick=41)
    assert set(r[0] for r in q(g, Q.STARTUP, me="research")) == {"ep_7a", "ep_7b", "f_http_pin"}
    assert q(g, Q.STARTUP, me="planner")[0][3:] == ["blocked", []]      # nothing left to wait on; promoted next round
    assert q(g, Q.PROMOTE_READY)[0][0] == 1
    assert q(g, Q.STARTUP, me="planner")[0][3] == "ready"
    assert q(g, Q.STARTUP, me="coder")[0][3:] == ["blocked", ["step_3"]]


def test_kill_planner_mid_rework_coder_stays_blocked(g, fx):
    open_session2(g, fx)
    q(g, Q.HEAL_FACTS, session="s2", tick=41)
    q(g, Q.PROMOTE_READY)

    # Planner process 1 claims, then dies (no COMPLETE).
    assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=50, lease=5, session="s2") == [["rework_step_3", None]]
    # Coder cannot start: its task is not ready and its blocker is unreplaced.
    assert q(g, Q.CLAIM, task="rework_a_requirements", me="coder", now=51, lease=5, session="s2") == []
    assert q(g, Q.STARTUP, me="coder")[0][3:] == ["blocked", ["step_3"]]
    # A restarted Planner cannot steal a live lease...
    assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=53, lease=5, session="s2b") == []
    # ...but takes over once it expires, and only one lease edge exists afterwards.
    assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=56, lease=5, session="s2b") == [["rework_step_3", "planner"]]
    assert q(g, "MATCH (:Task {id: 'rework_step_3'})-[c:CLAIMED_BY]->() RETURN count(c), c.session")[0] == [1, "s2b"]

    spec = fx["rework"]["step_3"]
    rework(g, "step_3", "planner", spec["text"], spec["reads"], 57, "s2b")
    q(g, Q.COMPLETE, task="rework_step_3", me="planner", tick=57, now=57, session="s2b")
    assert q(g, Q.PROMOTE_READY)[0][0] == 1                             # now the Coder unblocks, in order
    assert q(g, Q.CLAIM, task="rework_a_requirements", me="coder", now=58, lease=5, session="s2") == [["rework_a_requirements", None]]


def test_rework_refuses_to_cite_unreplaced_quarantined_memory(g, fx):
    open_session2(g, fx)
    with pytest.raises(ValueError, match="f_http_client"):
        rework(g, "step_3", "planner", "redo", ["f_http_client", "f_deps"], 60, "s2")


# ---------------------------------------------------------------- CLI
def test_cli_runs_the_three_commands_end_to_end(fx):
    import subprocess
    import sys

    def run(*args):
        r = subprocess.run([sys.executable, "-m", "quarantine.cli", *args, "--graph", "quarantine_cli_test"],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return r.stdout

    ex = fx["expected"]
    try:
        assert "session 1 done - 0 processes running" in run("session1")
        out = run("flag", fx["flag"]["doc"])
        assert f"precise {ex['precise']} | per-agent {ex['naive_per_agent']} | time-based {ex['naive_time_based']}" in out
        out = run("session2", "--kill-planner")
        assert "took over lease from planner" in out
        assert f"rounds {ex['session2_round_changes']}, {ex['memories_after_session2']} memories" in out
    finally:
        connect("quarantine_cli_test").delete()


def test_other_docs_have_their_own_hand_derived_closures(g, fx):
    """Independent of the hero numbers: closures worked out by hand from the fixture's read sets."""
    flag = fx["flag"]
    q(g, Q.FLAG_DOC, doc="doc_5", reason="control", tick=flag["tick"])
    q(g, Q.TAINT_CLOSURE, doc="doc_5", tick=flag["tick"])
    # doc_5 -> ep_5 -> f_http_client (cites ep_5) -> step_3 (reads it) -> a_requirements (reads step_3)
    assert quarantined(g) == {"ep_5", "f_http_client", "step_3", "a_requirements"}


def test_flagging_a_doc_nothing_read_quarantines_nothing(g, fx):
    q(g, "CREATE (:Doc {id: 'doc_unused', flagged: false})")
    q(g, Q.FLAG_DOC, doc="doc_unused", reason="control", tick=40)
    precise, ids_ = q(g, Q.TAINT_CLOSURE, doc="doc_unused", tick=40)[0]
    assert precise == 0 and ids_ == [] and quarantined(g) == set()
    assert q(g, Q.NAIVE_PER_AGENT, doc="doc_unused")[0][0] == 0         # baselines must return a row, not crash the CLI/page
    assert q(g, Q.NAIVE_TIME_BASED, doc="doc_unused")[0][0] == 0


def test_heal_needs_two_clean_episodes_and_takes_the_clean_majority(g, fx):
    """Boundary of the >= 2 rule, hand-derived. Flag doc_2 (a *good* doc) instead of doc_7:
    f_http_usage is supported by ep_2 (now red) and ep_8 -> exactly 1 clean -> must not heal.
    f_http_client is supported by ep_2 (red), ep_5, ep_7a, ep_8 -> 3 clean -> heals, and the
    clean majority claim is `requests` (ep_5, ep_8) over `reqeusts` (ep_7a)."""
    flag = fx["flag"]
    q(g, Q.FLAG_DOC, doc="doc_2", reason="control", tick=flag["tick"])
    q(g, Q.TAINT_CLOSURE, doc="doc_2", tick=flag["tick"])
    rows = {r[0]: r for r in q(g, Q.SUPPORT_AND_HEALABLE)}
    assert (rows["f_http_usage"][1], rows["f_http_usage"][2]) == (1, False)
    assert (rows["f_http_client"][1], rows["f_http_client"][2]) == (3, True)
    healed = {r[0]: r[1] for r in q(g, Q.HEAL_FACTS, session="s2", tick=41)}
    assert healed == {"f_http_client_v2": "requests"}


# ---------------------------------------------------------------- findings from the independent review
def test_rework_refuses_any_quarantined_or_missing_read_even_after_a_heal(g, fx):
    """The guard used to allow citing poisoned memory once it had a replacement, and nonexistent ids."""
    open_session2(g, fx)
    q(g, Q.HEAL_FACTS, session="s2", tick=41)                          # f_http_client now has a clean twin
    for reads in (["f_http_client", "f_deps"], ["f_http_clinet_v2", "f_deps"]):
        with pytest.raises(ValueError):
            rework(g, "step_3", "planner", "redo", reads, 60, "s2")
    assert q(g, "MATCH (m:Memory {id: 'step_3_v2'}) RETURN count(m)")[0][0] == 0
    assert audits_clean(g) == [0, 0, 0]


def _synthetic_fact(g, fid: str, clean_claims: list[str]):
    """A quarantined Fact (its own poisoned episode is red) plus clean episodes with the given claims."""
    q(g, "MATCH (a:Agent {name: 'research'}) "
         "CREATE (f:Memory:Fact {id: $fid, tick: 90, subject: 's', slot: $fid, value: 'bad', quarantined: true})"
         "<-[:AUTHORED]-(a)", fid=fid)
    q(g, "MATCH (f:Fact {id: $fid}) CREATE (e:Memory:Episode {id: $fid + '_bad', tick: 80, quarantined: true}) "
         "CREATE (f)-[:CONSOLIDATED_FROM {claim: 'bad'}]->(e)", fid=fid)
    for i, claim in enumerate(clean_claims):
        q(g, "MATCH (f:Fact {id: $fid}) CREATE (e:Memory:Episode {id: $eid, tick: 81, quarantined: false}) "
             "CREATE (f)-[:CONSOLIDATED_FROM {claim: $claim}]->(e)", fid=fid, eid=f"{fid}_{i}", claim=claim)


def test_heal_takes_a_strict_plurality_and_counts_only_agreeing_episodes(g, fx):
    _synthetic_fact(g, "f_plural", ["zzz", "zzz", "aaa"])
    _synthetic_fact(g, "f_tie", ["zzz", "aaa"])
    _synthetic_fact(g, "f_lone", ["zzz"])
    _synthetic_fact(g, "f_tie22", ["zzz", "zzz", "aaa", "aaa"])        # two claims, two supporters each: no winner
    rows = {r[0]: r for r in q(g, Q.SUPPORT_AND_HEALABLE)}
    assert [rows[f][2] for f in ("f_plural", "f_tie", "f_lone", "f_tie22")] == [True, False, False, False]
    healed = q(g, Q.HEAL_FACTS, session="s2", tick=41)
    assert healed == [["f_plural_v2", "zzz", 2]]                        # support is the two that agree, not all three
    assert q(g, "MATCH (:Fact {id: 'f_plural_v2'})-[c:CONSOLIDATED_FROM]->() WHERE c.rejected IS NULL RETURN count(c)")[0][0] == 2
    # the clean dissent is recorded too, marked rejected, so the vote is traceable (review finding)
    assert q(g, "MATCH (:Fact {id: 'f_plural_v2'})-[c:CONSOLIDATED_FROM {rejected: true}]->(e) RETURN c.claim, e.id")[0] == ["aaa", "f_plural_2"]
    assert q(g, "MATCH (f:Fact {id: 'f_plural_v2'}) RETURN f.runner_up_count, f.rule")[0] == [1, "strict plurality of clean episodes, at least 2"]
    assert q(g, "MATCH (m:Memory {id: 'f_tie_v2'}) RETURN count(m)")[0][0] == 0


def test_zombie_complete_cannot_close_a_task_and_rework_is_idempotent(g, fx):
    open_session2(g, fx)
    q(g, Q.HEAL_FACTS, session="s2", tick=41)
    q(g, Q.PROMOTE_READY)
    assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=50, lease=5, session="s2")
    assert q(g, Q.CLAIM, task="rework_step_3", me="coder", now=60, lease=5, session="s2c") == []   # not its author
    assert q(g, Q.CLAIM, task="rework_step_3", me="planner", now=56, lease=5, session="s2b")      # takeover
    # the live holder cannot close it without writing the replacement first
    assert q(g, Q.COMPLETE, task="rework_step_3", me="planner", tick=57, now=57, session="s2b") == []
    assert q(g, "MATCH (t:Task {id: 'rework_step_3'}) RETURN t.state")[0][0] == "claimed"
    spec = fx["rework"]["step_3"]
    rework(g, "step_3", "planner", spec["text"], spec["reads"], 57, "s2b")
    rework(g, "step_3", "planner", spec["text"], spec["reads"], 58, "s2b")                         # retried write
    assert q(g, "MATCH (m:Memory {id: 'step_3_v2'}) RETURN count(m)")[0][0] == 1
    assert read_set(g, "step_3_v2") == set(spec["reads"])
    assert q(g, "MATCH (:Memory {id: 'step_3_v2'})-[r:INFLUENCED_BY]->() RETURN count(r)")[0][0] == len(spec["reads"])
    # the replacement now exists, but the dead process (old session) still cannot close the task
    assert q(g, Q.COMPLETE, task="rework_step_3", me="planner", tick=58, now=58, session="s2") == []
    assert q(g, "MATCH (t:Task {id: 'rework_step_3'}) RETURN t.state")[0][0] == "claimed"
    assert q(g, Q.COMPLETE, task="rework_step_3", me="planner", tick=58, now=58, session="s2b")
    assert q(g, Q.PROMOTE_READY)[0][0] == 1                                                        # Coder unblocks


def test_two_advisories_and_unscripted_docs_do_not_crash_the_cli_or_page(fx):
    import subprocess
    import sys

    from web.server import receipt, snapshot

    graph = "quarantine_two_flags_test"

    def run(*args, ok=True):
        r = subprocess.run([sys.executable, "-m", "quarantine.cli", *args, "--graph", graph],
                           capture_output=True, text=True, timeout=60)
        assert (r.returncode == 0) == ok, r.stderr + r.stdout
        return r.stdout

    try:
        run("session1")
        run("flag", "doc_7")
        out = run("flag", "doc_4")                                       # used to IndexError on the second advisory
        g = connect(graph)
        assert ids(q(g, "MATCH (m:Memory {quarantined: true}) RETURN m.id")) == set(fx["expected"]["closure_ids"]) | {
            "ep_4", "f_api", "step_4", "step_5", "a_fetch_py"}
        assert "receipt a_fetch_py" in out and "receipt a_requirements" not in out   # only this advisory's receipts
        snap = snapshot(g)
        assert snap["counters"] is None                                  # two advisories: no single story to count
        assert receipt(g, "a_requirements")["hops"][-1] == "doc_7"       # receipt goes to the doc it actually reaches
        assert receipt(g, "a_fetch_py")["hops"][-1] == "doc_4"
        assert receipt(g, "a_scaffold")["shape"] == "not_in_graph"       # clean memory: an answer shape, not null
        out = run("session2")                                            # step_4 has no scripted rework: derived from the graph
        assert "fixpoint:" in out and "a_fetch_py_v2" in out and "step_4_v2" in out
    finally:
        connect(graph).delete()
