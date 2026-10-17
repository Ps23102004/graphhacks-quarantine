"""MCP tool server: a fixed, read-only tool catalog over the Quarantine graph.

The agent never writes Cypher. Every tool runs a human-written query from quarantine/answers.py or
quarantine/queries.py through the read-only path, resolves its arguments against the graph first, and
answers in one of four shapes: path, memory, not_in_graph, unknown.

Run:
    uv run python -m quarantine.mcp_server
"""
from __future__ import annotations

import os
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import WithJsonSchema
from quarantine.agent_runtime import recovery_status
from quarantine.answers import WITHHELD, blast_radius as _blast_radius
from quarantine.answers import recall as _recall
from quarantine.answers import why_connected as _why_connected
from quarantine.answers import why_quarantined
from quarantine.loader import connect

mcp = FastMCP("quarantine-memory")

# advertised as a string, but validated by the tool itself: a null, number, list or missing id gets the "unknown" shape,
# not a protocol error raised before the tool's own guard can run
Id = Annotated[Any, WithJsonSchema({"type": "string"})]

def graph_name() -> str:
    """Resolved per call so one server process can be re-pointed (and tests can set it) without re-import."""
    return os.environ.get("QUARANTINE_GRAPH", "quarantine")


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
def inspect_quarantined_memories() -> dict:
    """List all quarantined memories and why they were quarantined."""
    g = connect(graph_name())
    query = """
    MATCH (m:Memory {quarantined: true})<-[:AUTHORED]-(a:Agent)
    OPTIONAL MATCH (m)-[:SUPERSEDES]->(old:Memory)
    RETURN m.id, labels(m)[1], a.name, m.tick
    ORDER BY m.tick
    """
    rows = _ro_query(g, query)
    # ids and provenance only: the quarantined text itself may be the injection, so it never reaches an agent
    items = [{"id": r[0], "kind": r[1], "agent": r[2], "learned_tick": r[3], "content": WITHHELD} for r in rows]
    if not items:
        return {"shape": "not_in_graph", "answer": "no memory in this graph is quarantined (the graph says so; it is not a clean bill of health)", "items": []}
    return {"shape": "memory", "answer": f"{len(items)} quarantined memories, each with the tick it was learned", "items": items}


@mcp.tool()
def trace_provenance_receipt(memory_id: Id = None) -> dict:
    """Why is this memory quarantined? Answer shapes: path (hops + sentence), not_in_graph (clean memory),
    unknown (id does not resolve; nothing runs). The argument is resolved against the graph before any query."""
    if not memory_id or not isinstance(memory_id, str):
        return {"shape": "unknown", "answer": f"unknown memory: {memory_id!r} is not a valid id; nothing was run",
                "entity": repr(memory_id), "error": f"Invalid memory_id: {memory_id!r}"}
    out = why_quarantined(connect(graph_name()), memory_id)
    if out["shape"] == "unknown":
        out["error"] = out["answer"]                                     # the one shape that is also an error
    elif out["shape"] == "path":
        out["edge_types"] = out["via"]
    return out


@mcp.tool()
def why_connected(from_id: Id = None, to_id: Id = None) -> dict:
    """How does A lead to B? Fewest-hops (unweighted) path over provenance edges via algo.SPpaths; shortestPath only if the procedure raises.
    Both ids are resolved first: an unresolved id returns shape "unknown" and nothing runs."""
    if not isinstance(from_id, str) or not isinstance(to_id, str) or not from_id or not to_id:
        return {"shape": "unknown", "answer": "unknown entity: from_id and to_id must be non-empty strings; nothing was run",
                "entity": repr((from_id, to_id)), "error": "from_id and to_id must be non-empty strings"}
    return _why_connected(connect(graph_name()), from_id, to_id)


@mcp.tool()
def recall(memory_id: Id = None) -> dict:
    """What does this memory say? Answered from memory with when it was learned (tick, session, author),
    or shape "unknown" if the id does not resolve."""
    if not isinstance(memory_id, str) or not memory_id:
        return {"shape": "unknown", "answer": "unknown memory: memory_id must be a non-empty string; nothing was run",
                "entity": repr(memory_id), "error": "memory_id must be a non-empty string"}
    return _recall(connect(graph_name()), memory_id)


@mcp.tool()
def blast_radius(doc_id: Id = None) -> dict:
    """'And then': every memory derived from this document, read-only (what the harness would quarantine if flagged).
    Shape not_in_graph when nothing derives from it; unknown when the document does not resolve."""
    if not isinstance(doc_id, str) or not doc_id:
        return {"shape": "unknown", "answer": "unknown document: doc_id must be a non-empty string; nothing was run",
                "entity": repr(doc_id), "error": "doc_id must be a non-empty string"}
    return _blast_radius(connect(graph_name()), doc_id)


@mcp.tool()
def get_recovery_status() -> dict:
    """Recovery status read from the graph: shape "memory" (answered from stored state, with the tick it is current to)."""
    g = connect(graph_name())
    status = _recovery(g)
    return status


def _recovery(g) -> dict:
    try:
        status = recovery_status(g)
    except Exception as e:  # noqa: BLE001  (graph missing: an honest "not in the graph"; anything else, the real error)
        if "empty key" in str(e).lower() or "not exist" in str(e).lower():
            return {"shape": "not_in_graph", "answer": f"graph {graph_name()!r} does not exist on this server", "graph": graph_name()}
        return {"shape": "unknown", "answer": f"recovery status unavailable for graph {graph_name()!r}: {e}",
                "error": str(e), "graph": graph_name()}
    # "as of" = the latest write the status reflects: memory, flag, quarantine and task ticks alike
    row = _ro_query(g, "MATCH (n) WHERE n:Memory OR n:Doc OR n:Task RETURN max(n.tick), max(n.flag_tick), "
                       "max(n.quarantine_tick), max(n.created_tick), max(n.done_tick)")
    tick = max((t for t in (row[0] if row else []) if t is not None), default=None)
    status.update(shape="memory", answer=f"recovery status as of tick {tick}", learned_tick=tick)
    return status


if __name__ == "__main__":
    mcp.run()
