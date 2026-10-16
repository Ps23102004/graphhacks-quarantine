"""The graph must agree with the independent oracle on worlds nobody tuned a number for."""
from __future__ import annotations

import pytest

from quarantine import queries as Q
from quarantine.heldout import evaluate_world, run, summarize
from quarantine.loader import connect, load, q
from quarantine.worldgen import make_chain_world, make_world, oracle_tainted


@pytest.mark.parametrize("mode,deep", [("declared", False), ("cumulative", False), ("declared", True)])
def test_graph_equals_oracle_on_unseen_worlds(mode, deep):
    cases = run(range(2000, 2025), mode, deep, graph=f"heldout_test_{mode}_{deep}")
    bad = [(c.seed, c.doc, c.mismatches) for c in cases if c.mismatches]
    assert not bad, bad[:3]
    assert len(cases) > 150                                            # many (world, flagged doc) pairs, not a few


def test_closure_has_no_hop_bound():
    """Regression for a silent false negative: a *1..10 bound left poisoned memories at depth > 10 'clean'."""
    g = connect("heldout_chain_test")
    try:
        g.delete()
    except Exception:  # noqa: BLE001
        pass
    g = connect("heldout_chain_test")
    try:
        world = make_chain_world(40)
        cases = evaluate_world(g, world)
        assert all(not c.mismatches for c in cases), [c.mismatches for c in cases if c.mismatches][:1]
        q(g, Q.FLAG_DOC, doc="doc_1", reason="t", tick=900)
        q(g, "MATCH (m:Memory) SET m.quarantined = false")
        precise, _ = q(g, Q.TAINT_CLOSURE, doc="doc_1", tick=900)[0]
        assert precise == len(oracle_tainted(world, "doc_1")) == 1 + 1 + 40 + 1   # episode, fact, 40 steps, artifact
        hops, length, _ = q(g, Q.RECEIPT, **{"from": "art_0", "doc": "doc_1"})[0]
        assert length == 43 and hops[0] == "art_0" and hops[-1] == "doc_1"       # the receipt is not capped either
    finally:
        connect("heldout_chain_test").delete()


def test_baselines_overwipe_on_unseen_worlds():
    """The headline claim, measured on data the demo never saw (not the hand-tuned 6 vs 25 vs 19)."""
    cases = run(range(3000, 3030), "declared", graph="heldout_test_stats")
    s = summarize(cases)
    assert s["mismatched"] == 0
    assert s["mean_precise_frac"] < s["mean_time_frac"] < s["mean_per_agent_frac"] + 0.2
    assert s["clean_lost_per_agent"] > 0.5 and s["clean_lost_time"] > 0.3   # naive wipes throw away most clean work
    assert s["clean_lost_per_agent"] > s["clean_lost_time"]


@pytest.mark.parametrize("mode,deep", [("declared", False), ("cumulative", False), ("declared", True)])
def test_whole_session2_pipeline_on_unseen_worlds(mode, deep):
    """Flag, closure, heal, claim, graph-derived rework, to a fixpoint: invariants hold on every (world, doc)."""
    from quarantine.heldout import run_pipelines
    total, fails = run_pipelines(range(5000, 5012), mode, deep, graph=f"heldout_pipe_{mode}_{deep}")
    assert total > 80 and not fails, fails[:2]


def test_rework_when_every_input_is_dead_does_not_crash_and_is_marked_ungrounded():
    """Found by held-out data: a step whose only inputs were poisoned beyond repair made the rework write raise."""
    from quarantine.heldout import run_pipeline
    g = connect("heldout_ungrounded_test")
    try:
        try:
            g.delete()
        except Exception:  # noqa: BLE001
            pass
        g = connect("heldout_ungrounded_test")
        world = make_world(4000)
        load(g, world)
        assert run_pipeline(g, world, "doc_4") == []
        assert q(g, "MATCH (m:Memory {ungrounded: true}) RETURN count(m)")[0][0] >= 1
        assert q(g, "MATCH (m:Memory {ungrounded: true})-[r:INFLUENCED_BY]->() RETURN count(r)")[0][0] == 0
    finally:
        connect("heldout_ungrounded_test").delete()


def test_derived_rework_never_copies_quarantined_text_into_a_clean_memory():
    """Security review finding: copying the old text into a twin trusted as clean launders the poison."""
    from quarantine.heldout import run_pipeline
    from quarantine.loader import read_fixture
    fx = read_fixture()
    g = connect("heldout_launder_test")
    try:
        try:
            g.delete()
        except Exception:  # noqa: BLE001
            pass
        g = connect("heldout_launder_test")
        load(g, fx)
        assert run_pipeline(g, fx, "doc_4") == []                        # doc_4 has no scripted rework: derived from the graph
        for twin_id, old_id in (("step_4_v2", "step_4"), ("a_fetch_py_v2", "a_fetch_py")):
            twin_text, flag, old_text = q(g, "MATCH (t:Memory {id: $t}), (o:Memory {id: $o}) "
                                             "RETURN t.text, t.needs_regeneration, o.text", t=twin_id, o=old_id)[0]
            assert flag is True and old_text not in twin_text and "needs regeneration" in twin_text
    finally:
        connect("heldout_launder_test").delete()
