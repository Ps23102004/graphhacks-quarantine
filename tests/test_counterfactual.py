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


def test_demo_world_every_quarantined_memory_truly_changes():
    """f_http_client stores the typosquat `reqeusts`: without doc_7 it would have been `requests`. All six change."""
    w = read_fixture("fixture.yaml")
    flagged, truth = oracle_tainted(w, "doc_7"), truly_affected(w, "doc_7")
    assert truth == flagged and len(flagged) == 6


def test_unrecorded_influence_is_measured_not_hidden():
    """If agents were influenced by their whole context but declared only per-write reads, the closure misses some."""
    t = run(range(7000, 7006), "hidden", graph="cf_test_hidden")
    assert t.false_negatives                                          # the limit is real and the eval can see it
    assert not t.bad_receipts and not t.bad_clean_answers and not t.page_mismatch
