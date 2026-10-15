"""Load fixture.yaml into a FalkorDB graph and write scripted Session 2 rework.

The loader is the only place that knows the YAML shape. Everything the demo
does afterwards is a named statement in queries.py.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from falkordb import FalkorDB, Graph

FIXTURE = Path(__file__).resolve().parent.parent / "fixture.yaml"


def read_fixture(path: Path = FIXTURE) -> dict:
    return yaml.safe_load(path.read_text())


def connect(name: str = "quarantine", host: str = "localhost", port: int = 6379) -> Graph:
    return FalkorDB(host=host, port=port).select_graph(name)


def q(g: Graph, cypher: str, **params):
    """Run one statement, return result rows."""
    return g.query(cypher, params).result_set


# FalkorDB 6.0.2 rejects `CREATE (n $props)` (spike S5c) but accepts SET n += $props.
def _node(g: Graph, labels: str, props: dict) -> None:
    q(g, f"CREATE (n:{labels}) SET n += $p", p=props)


def _memory(g: Graph, labels: str, mid: str, author: str, session: str, props: dict) -> None:
    q(g, f"MATCH (a:Agent {{name: $author}}), (s:Session {{id: $session}}) "
         f"CREATE (m:Memory:{labels}) SET m += $p, m.id = $mid, m.quarantined = false "
         f"CREATE (a)-[:AUTHORED]->(m), (m)-[:RAN_IN]->(s)",
      author=author, session=session, p=props, mid=mid)


def _influenced_by(g: Graph, mid: str, reads: list[str], tick: int, session: str) -> None:
    for rid in reads:
        q(g, "MATCH (m:Memory {id: $mid}), (x:Memory {id: $rid}) "
             "CREATE (m)-[:INFLUENCED_BY {read_tick: $tick, session: $session}]->(x)",
          mid=mid, rid=rid, tick=tick, session=session)


def load(g: Graph, fx: dict) -> None:
    """Session 1, exactly as the fixture says. Idempotent only on an empty graph."""
    for sid, s in fx["sessions"].items():
        _node(g, "Session", {"id": sid, **s})
    for name, a in fx["agents"].items():
        _node(g, "Agent", {"name": name, **a})
    for did, d in fx["docs"].items():
        _node(g, "Doc", {"id": did, "flagged": False, **d})

    for eid, e in fx["episodes"].items():
        _memory(g, "Episode", eid, "research", "s1", {"tick": e["tick"], "text": e["text"]})
        q(g, "MATCH (m:Episode {id: $eid}), (d:Doc {id: $doc}) CREATE (m)-[:EXTRACTED_FROM]->(d)",
          eid=eid, doc=e["doc"])

    for fid, f in fx["facts"].items():
        _memory(g, "Fact", fid, "research", "s1",
                {"subject": f["subject"], "slot": f["slot"], "value": f["value"],
                 "tick": f["tick"], "support_total": len(f["support"])})
        for s in f["support"]:
            q(g, "MATCH (f:Fact {id: $fid}), (e:Episode {id: $ep}) "
                 "CREATE (f)-[:CONSOLIDATED_FROM {claim: $claim}]->(e)",
              fid=fid, ep=s["ep"], claim=s["claim"])

    for sid, s in fx["steps"].items():
        _memory(g, "PlanStep", sid, "planner", "s1", {"order": s["order"], "tick": s["tick"], "text": s["text"]})
        _influenced_by(g, sid, s["reads"], s["tick"], "s1")

    for aid, a in fx["artifacts"].items():
        _memory(g, "Artifact", aid, "coder", "s1", {"path": a["path"], "tick": a["tick"], "text": a["text"]})
        _influenced_by(g, aid, a["reads"], a["tick"], "s1")


def rework(g: Graph, old_id: str, by: str, text: str, reads: list[str], tick: int, session: str) -> str:
    """An agent's rework write: a new memory of the same kind that SUPERSEDES the
    quarantined one, with its own read set. Refuses a read set that still cites
    quarantined, unreplaced memory (the harness guard that stops re-poisoning)."""
    bad = q(g, "UNWIND $reads AS rid MATCH (x:Memory {id: rid, quarantined: true}) "
               "WHERE NOT (x)<-[:SUPERSEDES]-() RETURN collect(x.id)", reads=reads)[0][0]
    if bad:
        raise ValueError(f"read set cites unreplaced quarantined memory: {bad}")
    kind, = q(g, "MATCH (m:Memory {id: $id}) RETURN labels(m)[1]", id=old_id)[0]
    new_id = f"{old_id}_v2"
    q(g, f"MATCH (old:Memory {{id: $old}}), (a:Agent {{name: $by}}) "
         f"MERGE (s:Session {{id: $session}}) "   # a restarted process registers its own session
         f"CREATE (m:Memory:{kind} {{id: $new, tick: $tick, text: $text, quarantined: false, reworked_from: $old}}) "
         f"SET m.order = old.order, m.path = old.path "
         f"CREATE (m)-[:SUPERSEDES]->(old), (a)-[:AUTHORED]->(m), (m)-[:RAN_IN]->(s)",
      old=old_id, by=by, session=session, new=new_id, tick=tick, text=text)
    _influenced_by(g, new_id, reads, tick, session)
    return new_id
