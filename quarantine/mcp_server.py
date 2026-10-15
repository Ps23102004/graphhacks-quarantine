"""MCP tool server exposing read-only Cypher inspection for Quarantine.

Run:
    uv run python -m quarantine.mcp_server
"""
from __future__ import annotations

import os
from mcp.server.fastmcp import FastMCP
from quarantine.loader import connect, q

mcp = FastMCP("quarantine-memory")

GRAPH_NAME = os.environ.get("QUARANTINE_GRAPH", "quarantine")

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
    rows = q(g, query)
    return [
        {"id": r[0], "kind": r[1], "agent": r[2], "tick": r[3], "content": r[4] or r[5]}
        for r in rows
    ]

@mcp.tool()
def trace_provenance_receipt(memory_id: str) -> dict:
    """Trace shortestPath provenance from memory back to flagged prompt-injected document."""
    g = connect(GRAPH_NAME)
    query = """
    MATCH (m:Memory {id: $id}), (d:Doc {flagged: true})
    WITH shortestPath((m)-[:INFLUENCED_BY|CONSOLIDATED_FROM|EXTRACTED_FROM*..10]->(d)) AS p
    RETURN [n IN nodes(p) | n.id] AS hops, length(p) AS len, [r IN relationships(p) | type(r)] AS via
    """
    rows = q(g, query, id=memory_id)
    if not rows or not rows[0][0]:
        return {"error": f"No provenance path to flagged document for {memory_id}"}
    return {"hops": rows[0][0], "length": rows[0][1], "edge_types": rows[0][2]}

if __name__ == "__main__":
    mcp.run()
