"""Tests for MCP inspection server and stdio protocol."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import pytest

pytest.importorskip("mcp", reason="optional MCP SDK: run `uv sync --all-extras`")

from quarantine.loader import connect, q

PORT = int(os.environ.get("FALKORDB_PORT", 6393))
GRAPH = "quarantine_mcp_test"


@pytest.fixture(autouse=True)
def clean_graph():
    os.environ["QUARANTINE_GRAPH"] = GRAPH
    os.environ["FALKORDB_PORT"] = str(PORT)
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
        assert res == []
        assert missing_name not in db.list_graphs()

        receipt_res = srv.trace_provenance_receipt("some_id")
        assert "error" in receipt_res
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
    assert "error" in res
    assert "No provenance path to flagged document for ep_clean" in res["error"]


def test_inspect_quarantined_memories_returns_records():
    import quarantine.mcp_server as srv
    g = connect(GRAPH, port=PORT)
    q(g, "CREATE (a:Agent {name: 'researcher'})")
    q(g, "CREATE (m:Memory:Episode {id: 'ep_1', quarantined: true, tick: 5, text: 'content 1'})")
    q(g, "MATCH (a:Agent {name: 'researcher'}), (m:Memory {id: 'ep_1'}) CREATE (a)-[:AUTHORED]->(m)")

    memories = srv.inspect_quarantined_memories()
    assert len(memories) == 1
    assert memories[0]["id"] == "ep_1"
    assert memories[0]["agent"] == "researcher"
    assert memories[0]["tick"] == 5
    assert memories[0]["content"] == "content 1"


def test_get_recovery_status_deferred_or_delegated():
    import quarantine.mcp_server as srv
    status = srv.get_recovery_status()
    assert isinstance(status, dict)
    assert "mode" in status
    assert status["mode"] == "scripted"


def test_mcp_inspect_cli_stdio_handshake_and_tool_call():
    env = os.environ.copy()
    env["QUARANTINE_GRAPH"] = GRAPH
    env["FALKORDB_PORT"] = str(PORT)

    # 1. Test list command
    proc = subprocess.run(
        [sys.executable, "scripts/mcp_inspect.py", "list"],
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
        [sys.executable, "scripts/mcp_inspect.py", "call", "get_recovery_status"],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert proc2.returncode == 0, proc2.stderr
    status = json.loads(proc2.stdout)
    assert "mode" in status
