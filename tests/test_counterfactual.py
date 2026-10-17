"""Counterfactual replay: the graph must never miss a truly affected memory, never invent a receipt, never call a clean one red."""
from __future__ import annotations

import pytest

from quarantine.counterfactual import run, truly_affected
from quarantine.loader import read_fixture
from quarantine.worldgen import oracle_tainted


@pytest.mark.parametrize("mode,deep", [("declared", False), ("cumulative", False), ("declared", True)])
def test_no_false_negatives_no_invented_receipts_no_wrong_clean_answers(mode, deep):
    t = run(range(7000, 7012), mode, deep, graph=f"cf_test_{mode}_{deep}")
    assert t.runs > 80
    assert not t.false_negatives, t.false_negatives[:2]
    assert not t.bad_receipts, t.bad_receipts[:2]
    assert not t.bad_clean_answers, t.bad_clean_answers[:2]
    assert not t.page_mismatch, t.page_mismatch[:2]


def test_demo_world_five_of_six_truly_change_and_the_sixth_is_a_conservative_flag():
    """Stated in the README: 'quarantined' means touched by, not proven wrong."""
    w = read_fixture("fixture.yaml")
    for k in ("steps", "artifacts"):
        for m in w[k].values():
            m.setdefault("text", "")
    flagged, truth = oracle_tainted(w, "doc_7"), truly_affected(w, "doc_7")
    assert truth <= flagged                                           # never a false negative
    assert flagged - truth == {"f_http_client"} and len(flagged) == 6 and len(truth) == 5
