"""The four answer shapes from the organizers' build guide, and the fixed read-only tool catalog behind them.

Every answer an agent or a page gets back is one of:
  - "path":          answered, with the hops shown alongside the answer
  - "memory":        answered from memory, with when it was learned (tick and session)
  - "not_in_graph":  the graph holds no such connection (deliberately different from "nothing is wrong")
  - "unknown":       the entity does not resolve to a real node; nothing ran

Rules this file enforces (see docs/GUIDELINE-CONFORMANCE.md):
  - the agent never writes Cypher: every query here is human-written and fixed;
  - every argument is resolved against the graph before any query runs;
  - reads go through the read-only path (ro_query).
"""
from __future__ import annotations

from quarantine import queries as Q
from quarantine.loader import rq as _rq

PROVENANCE = "INFLUENCED_BY|CONSOLIDATED_FROM|EXTRACTED_FROM"

def rq(g, cypher: str, **params) -> list:
    """Read-only query that treats a graph which does not exist yet as empty (RO_QUERY never creates a key)."""
    try:
        return _rq(g, cypher, **params)
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "empty key" in msg or "not exist" in msg:
            return []
        raise


# ---------------------------------------------------------------- shapes
def shape_path(answer: str, hops: list[str], via: list[str]) -> dict:
    return {"shape": "path", "answer": answer, "hops": hops, "via": via, "length": len(hops) - 1,
            "sentence": sentence(hops, via)}


def shape_memory(answer: str, memory_id: str, tick: int, session: str | None, agent: str | None) -> dict:
    return {"shape": "memory", "answer": answer, "memory": memory_id, "learned_tick": tick,
            "learned_session": session, "learned_by": agent}


def shape_not_in_graph(what: str) -> dict:
    return {"shape": "not_in_graph", "answer": f"The graph holds no such connection: {what}. "
                                               "That is a statement about the graph, not a clean bill of health."}


def shape_unknown(entity: str, kind: str = "entity") -> dict:
    # an over-length id is rejected before any lookup, so "does not resolve" would be a claim about the graph we never checked
    why = f"id longer than {MAX_ID} characters is not accepted" if isinstance(entity, str) and len(entity) > MAX_ID \
        else "does not resolve to a node"
    return {"shape": "unknown", "answer": f"unknown {kind}: {entity!r} {why}; nothing was run",
            "entity": entity}


VERBS = {"INFLUENCED_BY": "was written after reading", "CONSOLIDATED_FROM": "was consolidated from",
         "EXTRACTED_FROM": "was extracted from", "SUPERSEDES": "replaces"}


def sentence(hops: list[str], via: list[str]) -> str:
    """A traversal wearing a sentence: 'A was written after reading B, which was consolidated from C, ...'.
    Raises on a malformed path rather than silently dropping hops."""
    if len(via) != max(len(hops) - 1, 0):
        raise ValueError(f"path has {len(hops)} nodes but {len(via)} edges")
    if len(hops) < 2:
        return hops[0] if hops else ""
    verb = lambda t: VERBS.get(t, f"is linked by {t} to")  # noqa: E731
    parts = [f"{hops[0]} {verb(via[0])} {hops[1]}"]
    for t, h in zip(via[1:], hops[2:]):
        parts.append(f"which {verb(t)} {h}")
    return ", ".join(parts) + "."


# ---------------------------------------------------------------- resolvers (run before any query)
MAX_ID = 256


def valid_id(x) -> bool:
    """Only a short, NUL-free, UTF-8 encodable string can be a node id; anything else is "unknown" without a query."""
    if not isinstance(x, str) or not x or len(x) > MAX_ID or "\x00" in x:
        return False
    try:
        x.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def resolve_memory(g, memory_id: str) -> dict | None:
    if not valid_id(memory_id):
        return None
    rows = rq(g, "MATCH (m:Memory {id: $id}) OPTIONAL MATCH (m)<-[:AUTHORED]-(a:Agent) OPTIONAL MATCH (m)-[:RAN_IN]->(s:Session) "
                 "RETURN m.id, labels(m)[1], m.tick, s.id, a.name, m.quarantined, m.text, m.value", id=memory_id)
    if not rows:
        return None
    i, kind, tick, sess, agent, quarantined, text, value = rows[0]
    return {"id": i, "kind": kind, "tick": tick, "session": sess, "agent": agent,
            "quarantined": bool(quarantined), "content": text or value or ""}


def resolve_doc(g, doc_id: str) -> dict | None:
    if not valid_id(doc_id):
        return None
    rows = rq(g, "MATCH (d:Doc {id: $id}) RETURN d.id, d.title, coalesce(d.flagged, false)", id=doc_id)
    return None if not rows else {"id": rows[0][0], "title": rows[0][1], "flagged": bool(rows[0][2])}


def resolve_node(g, node_id: str) -> dict | None:
    return resolve_memory(g, node_id) or resolve_doc(g, node_id)


# ---------------------------------------------------------------- the catalog
def why_quarantined(g, memory_id: str) -> dict:
    """Why is this memory red? A path to the flagged document, or 'not in the graph' if it is clean."""
    m = resolve_memory(g, memory_id)
    if m is None:
        return shape_unknown(memory_id, "memory")
    if not m["quarantined"]:
        return shape_not_in_graph(f"{memory_id} has no provenance path to any flagged document")
    # the advisory that quarantined it is recorded on the memory, so the receipt survives the doc being un-flagged
    docs = [r[0] for r in rq(g, "MATCH (m:Memory {id: $id}) WHERE m.quarantine_doc IS NOT NULL RETURN m.quarantine_doc", id=memory_id)]
    docs += [r[0] for r in rq(g, "MATCH (d:Doc {flagged: true}) RETURN d.id ORDER BY d.id") if r[0] not in docs]
    for doc in docs:
        rows = rq(g, Q.RECEIPT, **{"from": memory_id, "doc": doc})
        if rows and rows[0][0]:
            hops, _length, via = rows[0]
            return shape_path(f"{memory_id} is quarantined because its provenance reaches flagged {doc}", hops, via)
    return shape_not_in_graph(f"{memory_id} is flagged but no provenance path to a flagged document was found")


def why_connected(g, from_id: str, to_id: str) -> dict:
    """How does A lead to B? Fewest-hops path via algo.SPpaths over provenance edges (the sponsor's algorithm;
    unweighted: no weightProp is passed). shortestPath runs instead only if the procedure raises on this server;
    the result says which one answered ("method")."""
    a, b = resolve_node(g, from_id), resolve_node(g, to_id)
    if a is None:
        return shape_unknown(from_id)
    if b is None:
        return shape_unknown(to_id)
    rows: list = []
    method = "algo.SPpaths"
    try:
        rows = rq(g, "MATCH (a {id: $a}), (b {id: $b}) "
                     "CALL algo.SPpaths({sourceNode: a, targetNode: b, "
                     "relTypes: ['INFLUENCED_BY', 'CONSOLIDATED_FROM', 'EXTRACTED_FROM'], pathCount: 1}) "
                     "YIELD path RETURN [n IN nodes(path) | n.id], [r IN relationships(path) | type(r)]", a=from_id, b=to_id)
        if not rows:                                                    # the procedure ran and found nothing
            return shape_not_in_graph(f"no provenance path from {from_id} to {to_id}")
    except Exception:  # noqa: BLE001  (image without the procedure)
        method = "shortestPath"
        rows = rq(g, f"MATCH (a {{id: $a}}), (b {{id: $b}}) WITH shortestPath((a)-[:{PROVENANCE}*]->(b)) AS p "
                     "WHERE p IS NOT NULL RETURN [n IN nodes(p) | n.id], [r IN relationships(p) | type(r)]", a=from_id, b=to_id)
    if not rows or not rows[0][0]:
        return shape_not_in_graph(f"no provenance path from {from_id} to {to_id}")
    hops, via = rows[0]
    out = shape_path(f"{from_id} leads to {to_id} in {len(hops) - 1} hops", hops, via)
    out["method"] = method
    return out


def recall(g, memory_id: str) -> dict:
    """What does memory X say? Answered from memory, with when it was learned."""
    m = resolve_memory(g, memory_id)
    if m is None:
        return shape_unknown(memory_id, "memory")
    out = shape_memory(m["content"], m["id"], m["tick"], m["session"], m["agent"])
    out["quarantined"] = m["quarantined"]
    return out


def blast_radius(g, doc_id: str) -> dict:
    """'And then': everything this document led to, as the closure the harness would quarantine. Read-only."""
    d = resolve_doc(g, doc_id)
    if d is None:
        return shape_unknown(doc_id, "document")
    rows = rq(g, f"MATCH (d:Doc {{id: $doc}})<-[:{PROVENANCE}*1..]-(m:Memory) RETURN collect(DISTINCT m.id)", doc=doc_id)
    ids = sorted(rows[0][0]) if rows else []
    if not ids:
        return shape_not_in_graph(f"nothing in the graph was derived from {doc_id}")
    # "and then", member by member: each one's own path back to the document, rendered as a sentence
    chains = []
    for mid in ids:
        r = rq(g, Q.RECEIPT, **{"from": mid, "doc": doc_id})
        if r and r[0][0]:
            chains.append({"hops": r[0][0], "via": r[0][2], "sentence": sentence(r[0][0], r[0][2])})
    longest = max(chains, key=lambda c: len(c["hops"]), default={"hops": [], "via": []})
    return {"shape": "path", "answer": f"{len(ids)} memories derive from {doc_id}", "members": ids, "flagged": d["flagged"],
            "hops": longest["hops"], "via": longest["via"], "chains": chains,
            "sentence": f"{doc_id} led to {len(ids)} memories. Longest chain: {sentence(longest['hops'], longest['via'])}"}


CATALOG = {"why_quarantined": why_quarantined, "why_connected": why_connected, "recall": recall, "blast_radius": blast_radius}
