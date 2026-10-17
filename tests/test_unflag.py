"""A false alarm must be retractable, and retracting must leave exactly what the remaining advisories justify."""
from __future__ import annotations

import random

import pytest

from quarantine import queries as Q
from quarantine.loader import connect, load, q, read_fixture, unflag
from quarantine.worldgen import make_world, oracle_tainted
from web.server import snapshot


def fresh(name):
    g = connect(name)
    try:
        g.delete()
    except Exception:  # noqa: BLE001
        pass
    return connect(name)


def flag(g, doc, tick):
    q(g, Q.FLAG_DOC, doc=doc, reason="t", tick=tick)
    q(g, Q.TAINT_CLOSURE, doc=doc, tick=tick)
    q(g, Q.SUPPORT_AND_HEALABLE)
    q(g, Q.CREATE_REWORK_TASKS, tick=tick)
    q(g, Q.CREATE_BLOCKED_BY)


def red(g):
    return {n["id"] for n in snapshot(g)["nodes"] if n["red"]}


def test_demo_flag_then_unflag_restores_the_clean_graph():
    g = fresh("unflag_demo")
    try:
        load(g, read_fixture("fixture.yaml"))
        before = snapshot(g)
        flag(g, "doc_7", 40)
        assert len(red(g)) == 6
        out = unflag(g, "doc_7")
        assert out == {"still_flagged": [], "quarantined": []}
        after = snapshot(g)
        assert not red(g) and after["flagged"] is None and after["counters"] is None
        assert after["nodes"] == before["nodes"] and after["docs"] == before["docs"]
        assert q(g, "MATCH (t:Task) RETURN count(t)")[0][0] == 0
    finally:
        connect("unflag_demo").delete()


@pytest.mark.parametrize("seed", range(8000, 8012))
def test_unflag_one_of_several_leaves_exactly_the_rest(seed):
    r = random.Random(seed)
    world = make_world(seed)
    g = fresh(f"unflag_{seed}")
    try:
        load(g, world)
        docs = r.sample(sorted(world["docs"]), 3)
        for i, d in enumerate(docs):
            flag(g, d, 900 + i)
        assert red(g) == set().union(*(oracle_tainted(world, d) for d in docs))
        gone = r.choice(docs)
        out = unflag(g, gone)
        rest = [d for d in docs if d != gone]
        want = set().union(*(oracle_tainted(world, d) for d in rest))
        assert red(g) == want == set(out["quarantined"]), (seed, gone, rest)
        assert set(out["still_flagged"]) == set(rest)
        for d in rest:
            unflag(g, d)
        assert red(g) == set()
        assert q(g, "MATCH (t:Task) RETURN count(t)")[0][0] == 0
        for audit in (Q.AUDIT_CLEAN_NEVER_CITES_QUARANTINED, Q.AUDIT_CLOSURE_IS_CLOSED):
            assert q(g, audit)[0][0] == 0
    finally:
        connect(f"unflag_{seed}").delete()


def test_unflag_refuses_after_healing_and_changes_nothing():
    g = fresh("unflag_late")
    try:
        load(g, read_fixture("fixture.yaml"))
        flag(g, "doc_7", 40)
        q(g, Q.HEAL_FACTS, session="s2", tick=41)
        snap = snapshot(g)
        with pytest.raises(RuntimeError, match="healing has already started"):
            unflag(g, "doc_7")
        assert snapshot(g) == snap
    finally:
        connect("unflag_late").delete()


def test_unflag_unknown_doc_is_an_error_not_a_silent_success():
    g = fresh("unflag_unknown")
    try:
        load(g, read_fixture("fixture.yaml"))
        with pytest.raises(KeyError):
            unflag(g, "doc_999")
    finally:
        connect("unflag_unknown").delete()
