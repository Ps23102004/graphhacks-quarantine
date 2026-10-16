"""MCP tool server: a fixed, read-only tool catalog over the Quarantine graph.

The agent never writes Cypher. Every tool runs a human-written query from quarantine/answers.py or
quarantine/queries.py through the read-only path, resolves its arguments against the graph first, and
answers in one of four shapes: path, memory, not_in_graph, unknown.

Run:
    uv run python -m quarantine.mcp_server
"""
from __future__ import annotations

import os
from mcp.server.fastmcp import FastMCP
from quarantine.answers import blast_radius as _blast_radius
from quarantine.answers import recall as _recall
from quarantine.answers import why_connected as _why_connected
from quarantine.answers import why_quarantined
from quarantine.loader import connect

mcp = FastMCP("quarantine-memory")

GRAPH_NAME = os.environ.get("QUARANTINE_GRAPH", "quarantine")


def _ro_query(g, cypher: str, **params) -> list:
    """Run read-only Cypher query using GRAPH.RO_QUERY.
    Handles missing graph key without creating it.
    """
    try:
        if hasattr(g, "ro_query"):
            return g.ro_query(cypher, params).result_set
        return g.query(cypher, params, read_only=True).result_set
    except Exception as e:
        msg = str(e).lower()
        if "empty key" in msg or "not exist" in msg:
            return []
        raise


@mcp.tool()
def inspect_quarantined_memories() -> list[dict]:
    """List all quarantined memories and why they were quarantined."""
    g = connect(GRAPH_NAME)
    query = """
    MATCH (m:Memory {quarantined: true})<-[:AUTHORED]-(a:Agent)
    OPTIONAL MATCH (m)-[:SUPERSEDES]->(old:Memory)
    RETURN m.id, labels(m)[1], a.name, m.tick, m.text, m.value
    ORDER BY m.tick
    """
    rows = _ro_query(g, query)
    return [
        {"id": r[0], "kind": r[1], "agent": r[2], "tick": r[3], "content": r[4] or r[5]}
        for r in rows
    ]


@mcp.tool()
def trace_provenance_receipt(memory_id: str) -> dict:
    """Why is this memory quarantined? Answer shapes: path (hops + sentence), not_in_graph (clean memory),
    unknown (id does not resolve; nothing runs). The argument is resolved against the graph before any query."""
    if not memory_id or not isinstance(memory_id, str):
        return {"shape": "unknown", "error": f"Invalid memory_id: {memory_id!r}"}
    out = why_quarantined(connect(GRAPH_NAME), memory_id)
    if out["shape"] != "path":                                          # keep the error key older clients read
        out["error"] = out["answer"] if out["shape"] == "unknown" else f"No provenance path to flagged document for {memory_id}"
    else:
        out["length"] = out["length"]; out["edge_types"] = out["via"]
    return out


@mcp.tool()
def why_connected(from_id: str, to_id: str) -> dict:
    """How does A lead to B? Weighted shortest path over provenance edges via algo.SPpaths (shortestPath fallback).
    Both ids are resolved first: an unresolved id returns shape "unknown" and nothing runs."""
    if not isinstance(from_id, str) or not isinstance(to_id, str) or not from_id or not to_id:
        return {"shape": "unknown", "error": "from_id and to_id must be non-empty strings"}
    return _why_connected(connect(GRAPH_NAME), from_id, to_id)


@mcp.tool()
def recall(memory_id: str) -> dict:
    """What does this memory say? Answered from memory with when it was learned (tick, session, author),
    or shape "unknown" if the id does not resolve."""
    if not isinstance(memory_id, str) or not memory_id:
        return {"shape": "unknown", "error": "memory_id must be a non-empty string"}
    return _recall(connect(GRAPH_NAME), memory_id)


@mcp.tool()
def blast_radius(doc_id: str) -> dict:
    """'And then': every memory derived from this document, read-only (what the harness would quarantine if flagged).
    Shape not_in_graph when nothing derives from it; unknown when the document does not resolve."""
    if not isinstance(doc_id, str) or not doc_id:
        return {"shape": "unknown", "error": "doc_id must be a non-empty string"}
    return _blast_radius(connect(GRAPH_NAME), doc_id)


@mcp.tool()
def get_recovery_status() -> dict:
    """Return graph-derived recovery status from core engine."""
    g = connect(GRAPH_NAME)
    for mod_name in ("quarantine", "quarantine.queries", "quarantine.loader", "quarantine.cli", "quarantine.agent_runtime"):
        try:
            mod = __import__(mod_name, fromlist=["recovery_status"])
            if hasattr(mod, "recovery_status"):
                return getattr(mod, "recovery_status")(g)
        except Exception:
            continue
    return {
        "error": "core recovery_status(g) not yet implemented by core partition",
        "mode": "scripted",
        "graph": GRAPH_NAME,
        "complete": False,
        "deferred": True,
    }


if __name__ == "__main__":
    mcp.run()
