"""Tests for MCP inspection server and stdio protocol."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import pytest

pytest.importorskip("mcp", reason="optional MCP SDK: run `uv sync --all-extras`")

from quarantine.loader import connect, q

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent                          # tests must not depend on the working directory
PORT = int(os.environ.get("FALKORDB_PORT", 6379))
GRAPH = "quarantine_mcp_test"


@pytest.fixture(autouse=True)
def clean_graph(monkeypatch):
    monkeypatch.setenv("QUARANTINE_GRAPH", GRAPH)                     # restored after each test: no leak into other files
    monkeypatch.setenv("FALKORDB_PORT", str(PORT))
    g = connect(GRAPH, port=PORT)
    try:
        g.delete()
    except Exception:
        pass
    yield
    try:
        g.delete()
    except Exception:
        pass


def test_mcp_server_import_and_registered_tools():
    import quarantine.mcp_server as srv
    assert srv.mcp.name == "quarantine-memory"
    tool_names = [t.name for t in srv.mcp._tool_manager.list_tools()]
    assert "inspect_quarantined_memories" in tool_names
    assert "trace_provenance_receipt" in tool_names
    assert "get_recovery_status" in tool_names


def test_missing_graph_does_not_create_key():
    import quarantine.mcp_server as srv
    from falkordb import FalkorDB
    missing_name = "quarantine_definitely_missing_graph"
    os.environ["QUARANTINE_GRAPH"] = missing_name
    db = FalkorDB(port=PORT)
    try:
        res = srv.inspect_quarantined_memories()
        assert res["shape"] == "not_in_graph" and res["items"] == []
        assert missing_name not in db.list_graphs()

        receipt_res = srv.trace_provenance_receipt("some_id")
        assert receipt_res["shape"] == "unknown" and "error" in receipt_res
        assert missing_name not in db.list_graphs()
    finally:
        os.environ["QUARANTINE_GRAPH"] = GRAPH


def test_trace_provenance_receipt_invalid_ids():
    import quarantine.mcp_server as srv
    assert "error" in srv.trace_provenance_receipt("")
    assert "error" in srv.trace_provenance_receipt(None)
    assert "error" in srv.trace_provenance_receipt(123)


def test_trace_provenance_receipt_multiple_flagged_docs():
    """Finding 7 regression test: multiple flagged docs must not produce false negative."""
    import quarantine.mcp_server as srv
    g = connect(GRAPH, port=PORT)
    # Create two flagged docs; memory m1 only has a path to d2
    q(g, "CREATE (d1:Doc {id: 'doc_clean', flagged: true})")
    q(g, "CREATE (d2:Doc {id: 'doc_bad', flagged: true})")
    q(g, "CREATE (m1:Memory:Episode {id: 'ep_test', quarantined: true})")
    q(g, "MATCH (m:Memory {id: 'ep_test'}), (d:Doc {id: 'doc_bad'}) CREATE (m)-[:EXTRACTED_FROM]->(d)")

    res = srv.trace_provenance_receipt("ep_test")
    assert "error" not in res
    assert res["hops"] == ["ep_test", "doc_bad"]
    assert res["length"] == 1
    assert res["edge_types"] == ["EXTRACTED_FROM"]


def test_trace_provenance_receipt_clean_memory_returns_error():
    import quarantine.mcp_server as srv
    g = connect(GRAPH, port=PORT)
    q(g, "CREATE (d:Doc {id: 'doc_flagged', flagged: true})")
    q(g, "CREATE (m:Memory:Episode {id: 'ep_clean', quarantined: false})")

    res = srv.trace_provenance_receipt("ep_clean")
    assert res["shape"] == "not_in_graph" and "error" not in res         # a clean memory is an answer, not an error
    assert "no provenance path" in res["answer"]


def test_inspect_quarantined_memories_returns_records():
    import quarantine.mcp_server as srv
    g = connect(GRAPH, port=PORT)
    q(g, "CREATE (a:Agent {name: 'researcher'})")
    q(g, "CREATE (m:Memory:Episode {id: 'ep_1', quarantined: true, tick: 5, text: 'content 1'})")
    q(g, "MATCH (a:Agent {name: 'researcher'}), (m:Memory {id: 'ep_1'}) CREATE (a)-[:AUTHORED]->(m)")

    res = srv.inspect_quarantined_memories()
    assert res["shape"] == "memory"
    memories = res["items"]
    assert len(memories) == 1
    assert memories[0]["id"] == "ep_1"
    assert memories[0]["agent"] == "researcher"
    assert memories[0]["learned_tick"] == 5
    assert "withheld" in memories[0]["content"] and "content 1" not in str(res)   # quarantined text never reaches the agent


def test_get_recovery_status_deferred_or_delegated():
    import quarantine.mcp_server as srv
    status = srv.get_recovery_status()
    assert isinstance(status, dict)
    assert status["shape"] in ("memory", "not_in_graph")
    if status["shape"] == "memory":
        assert status["mode"] == "scripted" and "learned_tick" in status


def test_mcp_inspect_cli_stdio_handshake_and_tool_call():
    env = os.environ.copy()
    env["QUARANTINE_GRAPH"] = GRAPH
    env["FALKORDB_PORT"] = str(PORT)

    # 1. Test list command
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "mcp_inspect.py"), "list"],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    import json
    tools = json.loads(proc.stdout)
    names = [t["name"] for t in tools]
    assert "inspect_quarantined_memories" in names
    assert "trace_provenance_receipt" in names
    assert "get_recovery_status" in names

    # 2. Test call command
    proc2 = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "mcp_inspect.py"), "call", "get_recovery_status"],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert proc2.returncode == 0, proc2.stderr
    status = json.loads(proc2.stdout)
    assert status["shape"] in ("memory", "not_in_graph")                  # a status answer, in one of the four shapes


FX = "fx_mcp_stdio"
SHAPES = ("path", "memory", "not_in_graph", "unknown")


def _stdio(env_graph: str, calls: list[tuple[str, dict]]):
    """List tools and call each through a real MCP stdio session (FastMCP output validation included)."""
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client

    async def run():
        env = os.environ.copy() | {"QUARANTINE_GRAPH": env_graph, "FALKORDB_PORT": str(PORT)}
        params = StdioServerParameters(command=sys.executable, args=["-m", "quarantine.mcp_server"], env=env)
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = (await s.list_tools()).tools
                return tools, [(n, await s.call_tool(n, a)) for n, a in calls]
    return asyncio.run(run())


def test_every_tool_answers_a_shape_over_real_stdio_session():
    g = connect(FX, port=PORT)
    try:
        q(g, "CREATE (a:Agent {name: 'research'})-[:AUTHORED]->(m:Memory:Episode {id: 'ep_x', tick: 3, text: 't', "
             "quarantined: true})-[:EXTRACTED_FROM]->(:Doc {id: 'doc_x', title: 'd', flagged: true})")
        calls = [("inspect_quarantined_memories", {}), ("trace_provenance_receipt", {"memory_id": "ep_x"}),
                 ("why_connected", {"from_id": "ep_x", "to_id": "doc_x"}), ("recall", {"memory_id": "ep_x"}),
                 ("blast_radius", {"doc_id": "doc_x"}), ("get_recovery_status", {}),
                 ("recall", {"memory_id": "nope"})]
        tools, results = _stdio(FX, calls)
        assert {t.name for t in tools} == {n for n, _ in calls}                  # a new tool must be added here
        for name, res in results:
            assert not res.isError, (name, res.content)
            out = json.loads(res.content[0].text)                                # a bare dict comes back as JSON text
            assert out["shape"] in SHAPES, (name, out)
    finally:
        g.delete()


def test_why_connected_description_says_unweighted():
    tools, _ = _stdio(FX, [])
    desc = next(t.description for t in tools if t.name == "why_connected")
    assert "unweighted" in desc.lower() and "Weighted" not in desc


def test_mcp_inspect_surfaces_the_tool_error_message():
    env = os.environ.copy() | {"QUARANTINE_GRAPH": FX, "FALKORDB_PORT": str(PORT)}
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "mcp_inspect.py"), "call", "no_such_tool"],
                          capture_output=True, text=True, env=env, timeout=15)
    assert proc.returncode == 1
    assert "TaskGroup" not in proc.stderr and "Error: Tool no_such_tool returned error: Unknown tool" in proc.stderr, proc.stderr


def test_over_length_id_that_exists_is_not_called_unresolved():
    from quarantine.answers import recall
    g = connect(FX + "_long", port=PORT)
    long_id = "f_" + "x" * 300
    try:
        q(g, "CREATE (:Memory:Fact {id: $id, tick: 1, value: 'v', quarantined: false})", id=long_id)
        out = recall(g, long_id)
        assert out["shape"] == "unknown" and "does not resolve" not in out["answer"]
        assert "longer than 256 characters" in out["answer"]
    finally:
        g.delete()
