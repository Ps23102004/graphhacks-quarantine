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
        return g.ro_query(cypher, params).result_set
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
    items = [{"id": r[0], "kind": r[1], "agent": r[2], "learned_tick": r[3], "content": r[4] or r[5]} for r in rows]
    if not items:
        return {"shape": "not_in_graph", "answer": "no memory in this graph is quarantined (the graph says so; it is not a clean bill of health)", "items": []}
    return {"shape": "memory", "answer": f"{len(items)} quarantined memories, each with the tick it was learned", "items": items}


@mcp.tool()
def trace_provenance_receipt(memory_id: str) -> dict:
    """Why is this memory quarantined? Answer shapes: path (hops + sentence), not_in_graph (clean memory),
    unknown (id does not resolve; nothing runs). The argument is resolved against the graph before any query."""
    if not memory_id or not isinstance(memory_id, str):
        return {"shape": "unknown", "answer": f"unknown memory: {memory_id!r} is not a valid id; nothing was run",
                "entity": repr(memory_id), "error": f"Invalid memory_id: {memory_id!r}"}
    out = why_quarantined(connect(GRAPH_NAME), memory_id)
    if out["shape"] == "unknown":
        out["error"] = out["answer"]                                     # the one shape that is also an error
    elif out["shape"] == "path":
        out["edge_types"] = out["via"]
    return out


@mcp.tool()
def why_connected(from_id: str, to_id: str) -> dict:
    """How does A lead to B? Weighted shortest path over provenance edges via algo.SPpaths (shortestPath fallback).
    Both ids are resolved first: an unresolved id returns shape "unknown" and nothing runs."""
    if not isinstance(from_id, str) or not isinstance(to_id, str) or not from_id or not to_id:
        return {"shape": "unknown", "answer": "unknown entity: from_id and to_id must be non-empty strings; nothing was run",
                "entity": repr((from_id, to_id)), "error": "from_id and to_id must be non-empty strings"}
    return _why_connected(connect(GRAPH_NAME), from_id, to_id)


@mcp.tool()
def recall(memory_id: str) -> dict:
    """What does this memory say? Answered from memory with when it was learned (tick, session, author),
    or shape "unknown" if the id does not resolve."""
    if not isinstance(memory_id, str) or not memory_id:
        return {"shape": "unknown", "answer": "unknown memory: memory_id must be a non-empty string; nothing was run",
                "entity": repr(memory_id), "error": "memory_id must be a non-empty string"}
    return _recall(connect(GRAPH_NAME), memory_id)


@mcp.tool()
def blast_radius(doc_id: str) -> dict:
    """'And then': every memory derived from this document, read-only (what the harness would quarantine if flagged).
    Shape not_in_graph when nothing derives from it; unknown when the document does not resolve."""
    if not isinstance(doc_id, str) or not doc_id:
        return {"shape": "unknown", "answer": "unknown document: doc_id must be a non-empty string; nothing was run",
                "entity": repr(doc_id), "error": "doc_id must be a non-empty string"}
    return _blast_radius(connect(GRAPH_NAME), doc_id)


@mcp.tool()
def get_recovery_status() -> dict:
    """Recovery status read from the graph: shape "memory" (answered from stored state, with the tick it is current to)."""
    g = connect(GRAPH_NAME)
    status = _recovery(g)
    return status


def _recovery(g) -> dict:
    for mod_name in ("quarantine", "quarantine.queries", "quarantine.loader", "quarantine.cli", "quarantine.agent_runtime"):
        try:
            mod = __import__(mod_name, fromlist=["recovery_status"])
            if hasattr(mod, "recovery_status"):
                try:
                    status = getattr(mod, "recovery_status")(g)
                except Exception as e:  # noqa: BLE001  (graph missing: an honest "not in the graph", not a crash)
                    if "empty key" in str(e).lower() or "not exist" in str(e).lower():
                        return {"shape": "not_in_graph", "answer": f"graph {GRAPH_NAME!r} does not exist on this server", "graph": GRAPH_NAME}
                    raise
                tick = _ro_query(g, "MATCH (m:Memory) RETURN max(m.tick)")
                status.update(shape="memory", answer=f"recovery status as of tick {tick[0][0] if tick else None}",
                              learned_tick=tick[0][0] if tick else None)
                return status
        except Exception:
            continue
    return {"shape": "unknown", "answer": "recovery status is not available: no recovery_status implementation found",
            "error": "core recovery_status(g) not yet implemented", "graph": GRAPH_NAME}


if __name__ == "__main__":
    mcp.run()
