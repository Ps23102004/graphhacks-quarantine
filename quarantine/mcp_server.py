"""MCP tool server exposing read-only Cypher inspection for Quarantine.

Run:
    uv run python -m quarantine.mcp_server
"""
from __future__ import annotations

import os
from mcp.server.fastmcp import FastMCP
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
    """Trace shortestPath provenance from memory back to flagged prompt-injected document."""
    if not memory_id or not isinstance(memory_id, str):
        return {"error": f"Invalid memory_id: {memory_id!r}"}
    g = connect(GRAPH_NAME)
    query = """
    MATCH (m:Memory {id: $id}), (d:Doc {flagged: true})
    WITH shortestPath((m)-[:INFLUENCED_BY|CONSOLIDATED_FROM|EXTRACTED_FROM*]->(d)) AS p
    WHERE p IS NOT NULL
    RETURN [n IN nodes(p) | n.id] AS hops, length(p) AS len, [r IN relationships(p) | type(r)] AS via
    ORDER BY len ASC
    LIMIT 1
    """
    rows = _ro_query(g, query, id=memory_id)
    if not rows or not rows[0] or not rows[0][0]:
        return {"error": f"No provenance path to flagged document for {memory_id}"}
    return {"hops": rows[0][0], "length": rows[0][1], "edge_types": rows[0][2]}


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
