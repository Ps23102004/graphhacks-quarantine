"""A second, different world (customer-support crew) whose expected numbers were derived by hand from its read sets."""
from __future__ import annotations

from pathlib import Path

from quarantine import queries as Q
from quarantine.heldout import run_pipeline
from quarantine.loader import connect, load, q, read_fixture

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "support-crew.yaml"


def test_support_crew_matches_hand_derived_numbers_and_full_pipeline():
    fx = read_fixture(FIXTURE)
    ex = fx["expected"]
    g = connect("second_world_test")
    try:
        try:
            g.delete()
        except Exception:  # noqa: BLE001
            pass
        g = connect("second_world_test")
        load(g, fx)
        q(g, Q.FLAG_DOC, doc="kb_5", reason="t", tick=40)
        precise, ids_ = q(g, Q.TAINT_CLOSURE, doc="kb_5", tick=40)[0]
        assert precise == ex["precise"] == 7 and set(ids_) == set(ex["closure_ids"])
        assert q(g, Q.NAIVE_PER_AGENT, doc="kb_5")[0][0] == ex["naive_per_agent"] == 21
        assert q(g, Q.NAIVE_TIME_BASED, doc="kb_5")[0][0] == ex["naive_time_based"] == 17
        flags = {r[0]: (r[1], r[2]) for r in q(g, Q.SUPPORT_AND_HEALABLE)}
        assert flags["f_window"] == (3, True) and flags["f_receipt"] == (1, False)
        assert q(g, Q.HEAL_FACTS, session="s2", tick=41) == [["f_window_v2", "30", 3]]

        # whole Session 2 on this world (reset inside), invariants checked
        assert run_pipeline(g, fx, "kb_5") == []
        dead = {r[0] for r in q(g, "MATCH (m:Memory {quarantined: true}) WHERE NOT (m)<-[:SUPERSEDES]-() RETURN m.id")}
        assert dead == set(ex["dead"])
    finally:
        connect("second_world_test").delete()
