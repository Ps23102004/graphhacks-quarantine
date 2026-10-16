"""Does the build meet the organizers' guide ("How to Build an Agent That Reasons Over a Graph")?

One test per rule. Each docstring quotes the rule as distilled from the kickoff email; the test body is the
evidence. docs/GUIDELINE-CONFORMANCE.md maps rule -> evidence -> test.
"""
from __future__ import annotations

import ast
import inspect
import os
import re
from pathlib import Path

import pytest

from quarantine import answers, queries as Q
from quarantine.loader import connect, connection_kwargs, load, q, read_fixture, rq

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def fx():
    return read_fixture()


@pytest.fixture
def g(fx):
    g = connect("guideline_test")
    try:
        g.delete()
    except Exception:  # noqa: BLE001
        pass
    g = connect("guideline_test")
    load(g, fx)
    q(g, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)
    q(g, Q.TAINT_CLOSURE, doc="doc_7", tick=40)
    yield g
    g.delete()


# ---------------------------------------------------------------- rule 1
def test_rule1_agent_never_writes_cypher_fixed_catalog_with_validation(g):
    """Never let the agent write Cypher. Give it a fixed catalog of tools with human-written queries inside, and
    check every argument against the graph before running anything; a name that doesn't resolve returns
    "unknown" and nothing runs."""
    # (a) no tool takes Cypher as input: every catalog function's parameters are plain ids
    for name, fn in answers.CATALOG.items():
        params = [p for p in inspect.signature(fn).parameters if p != "g"]
        assert params and all(p.endswith("_id") for p in params), (name, params)
    # (b) the MCP server exposes no raw-query tool
    src = (ROOT / "quarantine" / "mcp_server.py").read_text()
    tools = re.findall(r"@mcp\.tool\(\)\s*\ndef (\w+)\(([^)]*)\)", src)
    assert tools and not any("cypher" in sig.lower() or "query" in sig.lower() for _, sig in tools), tools
    # (c) an unresolved argument returns "unknown" and nothing runs: the resolver is consulted and no query executes
    calls: list[str] = []
    real_rq = answers.rq
    answers.rq = lambda g_, cypher, **p: (calls.append(cypher), real_rq(g_, cypher, **p))[1]
    try:
        for fn, args in ((answers.why_quarantined, ("no_such",)), (answers.why_connected, ("no_such", "doc_7")),
                         (answers.recall, ("no_such",)), (answers.blast_radius, ("no_such_doc",))):
            calls.clear()
            out = fn(g, *args)
            assert out["shape"] == "unknown", out
            assert all("Memory {id: $id}" in c or "Doc {id: $id}" in c for c in calls), calls   # resolvers only
    finally:
        answers.rq = real_rq


# ---------------------------------------------------------------- rule 2
def test_rule2_reads_use_ro_query_and_one_graph_per_tenant(fx):
    """Reads go through ro_query (the read-only path), and one graph per tenant via select_graph."""
    # (a) the read path refuses writes
    g = connect("guideline_ro_test")
    try:
        q(g, "CREATE (:Marker {id: 'exists'})")                        # a graph has to exist for RO_QUERY to reach the parser
        with pytest.raises(Exception, match="(?i)read.?only|write"):
            rq(g, "CREATE (:Memory {id: 'smuggled'})")
        assert rq(g, "MATCH (m:Memory {id: 'smuggled'}) RETURN count(m)")[0][0] == 0
    finally:
        try:
            g.delete()
        except Exception:  # noqa: BLE001
            pass
    # (b) every read-only catalog function and every page/MCP read goes through rq / ro_query
    src = (ROOT / "quarantine" / "answers.py").read_text()
    assert " q(" not in src and "rq(" in src
    for path in ("web/server.py", "quarantine/mcp_server.py", "quarantine/agent_runtime.py"):
        assert "ro_query" in (ROOT / path).read_text(), path
    # (c) tenant isolation: two crews in two graphs, an advisory in one never touches the other
    a, b = connect("guideline_tenant_a"), connect("guideline_tenant_b")
    for x in (a, b):
        try:
            x.delete()
        except Exception:  # noqa: BLE001
            pass
    a, b = connect("guideline_tenant_a"), connect("guideline_tenant_b")
    try:
        load(a, fx)
        load(b, fx)
        q(a, Q.FLAG_DOC, doc="doc_7", reason="t", tick=40)
        assert q(a, Q.TAINT_CLOSURE, doc="doc_7", tick=40)[0][0] == 6
        assert rq(b, "MATCH (m:Memory {quarantined: true}) RETURN count(m)")[0][0] == 0
        assert rq(b, "MATCH (d:Doc {flagged: true}) RETURN count(d)")[0][0] == 0
        assert answers.why_quarantined(b, "a_requirements")["shape"] == "not_in_graph"
        assert answers.why_quarantined(a, "a_requirements")["shape"] == "path"
    finally:
        a.delete()
        b.delete()


# ---------------------------------------------------------------- rule 3
def test_rule3_local_to_live_is_environment_only(monkeypatch):
    """Local to live is trivial: FalkorDB Cloud is the managed version of the same database; the code moves
    across by changing a host and a port (plus the credentials Cloud requires)."""
    for k in ("FALKORDB_HOST", "FALKORDB_PORT", "FALKORDB_USERNAME", "FALKORDB_PASSWORD", "FALKORDB_TLS"):
        monkeypatch.delenv(k, raising=False)
    assert connection_kwargs() == {"host": "localhost", "port": 6379}
    monkeypatch.setenv("FALKORDB_HOST", "r-abc.instance.cloud.falkordb.io")
    monkeypatch.setenv("FALKORDB_PORT", "62345")
    monkeypatch.setenv("FALKORDB_USERNAME", "falkordb")
    monkeypatch.setenv("FALKORDB_PASSWORD", "example-not-a-real-secret")
    monkeypatch.setenv("FALKORDB_TLS", "1")
    kw = connection_kwargs()
    assert kw == {"host": "r-abc.instance.cloud.falkordb.io", "port": 62345, "username": "falkordb",
                  "password": "example-not-a-real-secret", "ssl": True}
    # and nothing in the code base hard-codes a host or port outside connect()
    for path in ROOT.glob("quarantine/*.py"):
        if path.name == "loader.py":
            continue
        assert "6379" not in path.read_text() and "FalkorDB(" not in path.read_text(), path


# ---------------------------------------------------------------- rule 4
def test_rule4_every_answer_is_one_of_four_shapes(g):
    """Every answer comes back in one of four shapes: answered with the path shown, answered from memory
    (with the date it was learned), "not in the graph" (deliberately different from "nothing is wrong"),
    or "unknown entity"."""
    shapes = set()
    out = answers.why_quarantined(g, "a_requirements")
    assert out["shape"] == "path" and out["hops"][0] == "a_requirements" and out["hops"][-1] == "doc_7"
    assert out["length"] == len(out["via"]) == 4 and out["sentence"].endswith("doc_7.")
    shapes.add(out["shape"])

    out = answers.recall(g, "f_http_client")
    assert out["shape"] == "memory" and out["learned_tick"] == 11 and out["learned_session"] == "s1"
    assert out["learned_by"] == "research" and out["answer"] == "reqeusts" and out["quarantined"] is True
    shapes.add(out["shape"])

    out = answers.why_quarantined(g, "a_fetch_py")                     # a real, clean memory
    assert out["shape"] == "not_in_graph" and "not a clean bill of health" in out["answer"]
    shapes.add(out["shape"])

    out = answers.why_quarantined(g, "a_fetch_pyy")                    # one typo away: a different shape
    assert out["shape"] == "unknown" and "nothing was run" in out["answer"]
    shapes.add(out["shape"])

    assert shapes == {"path", "memory", "not_in_graph", "unknown"}
    # every catalog function only ever returns these four shapes, on good and bad inputs alike
    for fn, good, bad in ((answers.why_quarantined, ("step_3",), ("x",)), (answers.why_connected, ("step_3", "doc_7"), ("step_3", "x")),
                          (answers.recall, ("step_3",), ("x",)), (answers.blast_radius, ("doc_7",), ("x",))):
        assert fn(g, *good)["shape"] in shapes and fn(g, *bad)["shape"] == "unknown"


# ---------------------------------------------------------------- rule 5
def test_rule5_graph_algorithm_is_a_tool_and_actually_runs(g):
    """Graph algorithms are free tools: shortest path via CALL algo.SPpaths is the one that earns its place
    fastest; "why are these connected" questions answer themselves."""
    out = answers.why_connected(g, "a_requirements", "doc_7")
    assert out["shape"] == "path" and out["method"] == "algo.SPpaths", out   # the procedure ran, not the fallback
    assert out["length"] == 4 and out["hops"][0] == "a_requirements" and out["hops"][-1] == "doc_7"
    assert set(out["hops"][1:-1]) <= {"step_3", "f_http_client", "ep_7a", "f_http_pin", "ep_7b"}
    # same length as the Cypher shortestPath receipt (two tied 4-hop paths exist; either is a valid answer)
    assert rq(g, Q.RECEIPT, **{"from": "a_requirements", "doc": "doc_7"})[0][1] == out["length"]
    # the question "why are these connected" is answered without any agent-written query: a sentence comes back
    assert out["sentence"].startswith("a_requirements was written after reading")
    # unconnected pairs are "not in the graph", not an error
    assert answers.why_connected(g, "a_fetch_py", "doc_7")["shape"] == "not_in_graph"


# ---------------------------------------------------------------- rule 6
def test_rule6_blast_radius_is_a_traversal_wearing_a_sentence(g):
    """Build for the question "and then": if the agent's job is following "A led to B which caused C",
    that's a traversal wearing a sentence, and that's where the graph wins."""
    s = answers.sentence(["a_requirements", "step_3", "f_http_client", "ep_7a", "doc_7"],
                         ["INFLUENCED_BY", "INFLUENCED_BY", "CONSOLIDATED_FROM", "EXTRACTED_FROM"])
    assert s == ("a_requirements was written after reading step_3, which was written after reading f_http_client, "
                 "which was consolidated from ep_7a, which was extracted from doc_7.")
    out = answers.blast_radius(g, "doc_7")
    assert out["shape"] == "path" and out["members"] == ["a_requirements", "ep_7a", "ep_7b", "f_http_client", "f_http_pin", "step_3"]
    assert out["sentence"].startswith("doc_7 led to 6 memories")
    # the same "and then" on a document nothing derived from is "not in the graph", not zero-with-a-shrug
    q(g, "CREATE (:Doc {id: 'doc_lonely', flagged: false})")
    assert answers.blast_radius(g, "doc_lonely")["shape"] == "not_in_graph"
