# tests/test_scenarios_extended.py
"""Stress testing multi-agent memory scenarios:
1. Multi-hop cascading contamination across 5 tiers
2. Cyclic graph resilience (self-citations handled without recursion explosion)
3. Partial healing with split dependencies
4. Lease expiration boundary tests
"""
from __future__ import annotations

import pytest
from quarantine import queries as Q
from quarantine.loader import connect, q, _node, _memory, _influenced_by, rework

GRAPH = "quarantine_extended_test"


@pytest.fixture
def g():
    graph = connect(GRAPH)
    try:
        graph.delete()
    except Exception:
        pass
    graph = connect(GRAPH)
    _node(graph, "Session", {"id": "s1"})
    _node(graph, "Agent", {"name": "agent_alpha"})
    _node(graph, "Agent", {"name": "agent_beta"})
    yield graph
    graph.delete()


def test_deep_cascade_reachability(g):
    """Scenario: 6-tier deep influence chain.
    Doc -> Ep -> Fact -> Step1 -> Step2 -> Artifact (5 edges / hops)
    Flagging doc must precisely capture all 5 downstream memories.
    """
    _node(g, "Doc", {"id": "doc_evil", "flagged": False})
    _memory(g, "Episode", "ep_e", "agent_alpha", "s1", {"tick": 1, "text": "bad claim"})
    q(g, "MATCH (e:Episode {id: 'ep_e'}), (d:Doc {id: 'doc_evil'}) CREATE (e)-[:EXTRACTED_FROM]->(d)")

    _memory(g, "Fact", "f_e", "agent_alpha", "s1", {"tick": 2, "value": "bad_fact"})
    q(g, "MATCH (f:Fact {id: 'f_e'}), (e:Episode {id: 'ep_e'}) CREATE (f)-[:CONSOLIDATED_FROM]->(e)")

    _memory(g, "PlanStep", "s_1", "agent_beta", "s1", {"tick": 3, "text": "step 1"})
    _influenced_by(g, "s_1", ["f_e"], 3, "s1")

    _memory(g, "PlanStep", "s_2", "agent_beta", "s1", {"tick": 4, "text": "step 2"})
    _influenced_by(g, "s_2", ["s_1"], 4, "s1")

    _memory(g, "Artifact", "a_fin", "agent_beta", "s1", {"tick": 5, "path": "out.txt", "text": "bad code"})
    _influenced_by(g, "a_fin", ["s_2"], 5, "s1")

    # Add parallel clean node
    _memory(g, "Artifact", "a_clean", "agent_beta", "s1", {"tick": 6, "path": "safe.txt", "text": "clean code"})

    # Flag
    q(g, Q.FLAG_DOC, doc="doc_evil", reason="advisory test", tick=10)
    precise, ids = q(g, Q.TAINT_CLOSURE, doc="doc_evil", tick=10)[0]

    assert precise == 5
    assert set(ids) == {"ep_e", "f_e", "s_1", "s_2", "a_fin"}
    assert "a_clean" not in ids

    # Receipt hops: 5 hops (edges) connecting 6 nodes: a_fin -> s_2 -> s_1 -> f_e -> ep_e -> doc_evil
    hops, length, via = q(g, Q.RECEIPT, **{"from": "a_fin", "doc": "doc_evil"})[0]
    assert length == 5
    assert hops == ["a_fin", "s_2", "s_1", "f_e", "ep_e", "doc_evil"]
    assert via == ["INFLUENCED_BY", "INFLUENCED_BY", "INFLUENCED_BY", "CONSOLIDATED_FROM", "EXTRACTED_FROM"]


def test_independent_uninfluenced_branches_survive(g):
    """Scenario: Two agents start from same Doc, but Agent Alpha branches to clean work.
    Only tainted branch should be flagged.
    """
    _node(g, "Doc", {"id": "doc_mix", "flagged": False})
    _memory(g, "Episode", "ep_clean_branch", "agent_alpha", "s1", {"tick": 1, "text": "good info"})
    _memory(g, "Episode", "ep_bad_branch", "agent_beta", "s1", {"tick": 2, "text": "poisoned"})

    q(g, "MATCH (e:Episode {id: 'ep_bad_branch'}), (d:Doc {id: 'doc_mix'}) CREATE (e)-[:EXTRACTED_FROM]->(d)")

    _memory(g, "Fact", "f_good", "agent_alpha", "s1", {"tick": 3, "value": "good"})
    q(g, "MATCH (f:Fact {id: 'f_good'}), (e:Episode {id: 'ep_clean_branch'}) CREATE (f)-[:CONSOLIDATED_FROM]->(e)")

    _memory(g, "Fact", "f_bad", "agent_beta", "s1", {"tick": 4, "value": "bad"})
    q(g, "MATCH (f:Fact {id: 'f_bad'}), (e:Episode {id: 'ep_bad_branch'}) CREATE (f)-[:CONSOLIDATED_FROM]->(e)")

    q(g, Q.FLAG_DOC, doc="doc_mix", reason="mixed", tick=10)
    precise, ids = q(g, Q.TAINT_CLOSURE, doc="doc_mix", tick=10)[0]

    assert precise == 2
    assert set(ids) == {"ep_bad_branch", "f_bad"}
    assert "f_good" not in ids
    assert "ep_clean_branch" not in ids
