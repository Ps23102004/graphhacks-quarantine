"""Load fixture.yaml into a FalkorDB graph and write scripted Session 2 rework.

The loader is the only place that knows the YAML shape. Everything the demo
does afterwards is a named statement in queries.py.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import yaml
from falkordb import FalkorDB, Graph

FIXTURE_CHECKOUT = Path(__file__).resolve().parent.parent / "fixture.yaml"
FIXTURE_INSTALLED = Path(sys.prefix) / "share" / "quarantine" / "fixture.yaml"
FIXTURE = FIXTURE_CHECKOUT if FIXTURE_CHECKOUT.exists() else FIXTURE_INSTALLED


def read_fixture(path: Path | str | None = None) -> dict:
    if path is not None:
        p = Path(path)
    elif FIXTURE_CHECKOUT.exists():
        p = FIXTURE_CHECKOUT
    elif FIXTURE_INSTALLED.exists():
        p = FIXTURE_INSTALLED
    else:
        p = FIXTURE_CHECKOUT
    return yaml.safe_load(p.read_text())


def validate_fixture(fx: dict) -> None:
    """Validate fixture structure, references, and temporal monotone properties."""
    required = ("sessions", "agents", "docs", "episodes", "facts", "steps", "artifacts")
    for sec in required:
        if sec not in fx or not isinstance(fx[sec], dict):
            raise ValueError(f"Fixture missing required dictionary section: {sec!r}")

    known_docs = set(fx["docs"].keys())
    known_memories: dict[str, int] = {}

    for eid, e in fx["episodes"].items():
        if e.get("doc") not in known_docs:
            raise ValueError(f"Episode {eid} references unknown doc: {e.get('doc')!r}")
        tick = e.get("tick")
        if not isinstance(tick, int) or tick <= 0:
            raise ValueError(f"Episode {eid} has invalid tick: {tick!r}")
        if eid in known_memories:
            raise ValueError(f"Duplicate memory ID: {eid!r}")
        known_memories[eid] = tick

    for fid, f in fx["facts"].items():
        tick = f.get("tick")
        if not isinstance(tick, int) or tick <= 0:
            raise ValueError(f"Fact {fid} has invalid tick: {tick!r}")
        if fid in known_memories:
            raise ValueError(f"Duplicate memory ID: {fid!r}")
        known_memories[fid] = tick
        for s in f.get("support", []):
            ep_id = s.get("ep")
            if ep_id not in fx["episodes"]:
                raise ValueError(f"Fact {fid} references unknown episode: {ep_id!r}")
            if known_memories[ep_id] >= tick:
                raise ValueError(f"Temporal violation: Fact {fid} (tick {tick}) cites later episode {ep_id}")

    for sid, s in fx["steps"].items():
        tick = s.get("tick")
        if not isinstance(tick, int) or tick <= 0:
            raise ValueError(f"Step {sid} has invalid tick: {tick!r}")
        if sid in known_memories:
            raise ValueError(f"Duplicate memory ID: {sid!r}")
        known_memories[sid] = tick
        for rid in s.get("reads", []):
            if rid not in known_memories:
                raise ValueError(f"Step {sid} references unknown memory in read set: {rid!r}")
            if known_memories[rid] >= tick:
                raise ValueError(f"Temporal violation: Step {sid} (tick {tick}) cites later memory {rid}")

    for aid, a in fx["artifacts"].items():
        tick = a.get("tick")
        if not isinstance(tick, int) or tick <= 0:
            raise ValueError(f"Artifact {aid} has invalid tick: {tick!r}")
        if aid in known_memories:
            raise ValueError(f"Duplicate memory ID: {aid!r}")
        known_memories[aid] = tick
        for rid in a.get("reads", []):
            if rid not in known_memories:
                raise ValueError(f"Artifact {aid} references unknown memory in read set: {rid!r}")
            if known_memories[rid] >= tick:
                raise ValueError(f"Temporal violation: Artifact {aid} (tick {tick}) cites later memory {rid}")


def connect(name: str = "quarantine", host: str | None = None, port: int | None = None) -> Graph:
    """FALKORDB_HOST/PORT let containers, tests, and scripts override connection parameters."""
    h = host if host is not None else os.environ.get("FALKORDB_HOST", "localhost")
    p = port if port is not None else int(os.environ.get("FALKORDB_PORT", 6379))
    return FalkorDB(host=h, port=p).select_graph(name)


def q(g: Graph, cypher: str, **params):
    """Run one write-capable statement, return result rows."""
    return g.query(cypher, params).result_set


def rq(g: Graph, cypher: str, **params):
    """Run one read-only statement using ro_query, return result rows."""
    if hasattr(g, "ro_query"):
        return g.ro_query(cypher, params).result_set
    return g.query(cypher, params, read_only=True).result_set


def _node(g: Graph, labels: str, props: dict) -> None:
    res = q(g, f"CREATE (n:{labels}) SET n += $p RETURN count(n)", p=props)
    if not res or res[0][0] == 0:
        raise RuntimeError(f"Failed to create node :{labels} with props {props}")


def _memory(g: Graph, labels: str, mid: str, author: str, session: str, props: dict) -> None:
    res = q(g, f"MATCH (a:Agent {{name: $author}}), (s:Session {{id: $session}}) "
               f"CREATE (m:Memory:{labels}) SET m += $p, m.id = $mid, m.quarantined = false "
               f"CREATE (a)-[:AUTHORED]->(m), (m)-[:RAN_IN]->(s) "
               f"RETURN count(m)",
            author=author, session=session, p=props, mid=mid)
    if not res or res[0][0] == 0:
        raise RuntimeError(f"Failed to create memory {mid} authored by {author} in session {session}")


def _influenced_by(g: Graph, mid: str, reads: list[str], tick: int, session: str) -> None:
    for rid in reads:
        res = q(g, "MATCH (m:Memory {id: $mid}), (x:Memory {id: $rid}) "
                   "CREATE (m)-[:INFLUENCED_BY {read_tick: $tick, session: $session}]->(x) "
                   "RETURN count(*)",
                mid=mid, rid=rid, tick=tick, session=session)
        if not res or res[0][0] == 0:
            raise ValueError(f"Failed to link INFLUENCED_BY from {mid} to missing {rid}")


def load(g: Graph, fx: dict, after_write=None) -> None:
    """Session 1, exactly as the fixture says. Idempotent only on an empty graph.
    after_write(memory_id) is called once each memory and its edges exist (the CLI prints from it)."""
    validate_fixture(fx)
    done = after_write or (lambda mid: None)
    for sid, s in fx["sessions"].items():
        _node(g, "Session", {"id": sid, **s})
    for name, a in fx["agents"].items():
        _node(g, "Agent", {"name": name, **a})
    for did, d in fx["docs"].items():
        _node(g, "Doc", {"id": did, "flagged": False, **d})

    for eid, e in fx["episodes"].items():
        _memory(g, "Episode", eid, e.get("agent", "research"), "s1", {"tick": e["tick"], "text": e["text"]})
        res = q(g, "MATCH (m:Episode {id: $eid}), (d:Doc {id: $doc}) CREATE (m)-[:EXTRACTED_FROM]->(d) RETURN count(*)",
                eid=eid, doc=e["doc"])
        if not res or res[0][0] == 0:
            raise ValueError(f"Failed to link episode {eid} to doc {e['doc']}")
        done(eid)

    for fid, f in fx["facts"].items():
        _memory(g, "Fact", fid, f.get("agent", "research"), "s1",
                {"subject": f["subject"], "slot": f["slot"], "value": f["value"],
                 "tick": f["tick"], "support_total": len(f["support"])})
        for s in f["support"]:
            res = q(g, "MATCH (f:Fact {id: $fid}), (e:Episode {id: $ep}) "
                       "CREATE (f)-[:CONSOLIDATED_FROM {claim: $claim}]->(e) RETURN count(*)",
                    fid=fid, ep=s["ep"], claim=s["claim"])
            if not res or res[0][0] == 0:
                raise ValueError(f"Failed to link fact {fid} to episode {s['ep']}")
        done(fid)

    for sid, s in fx["steps"].items():
        _memory(g, "PlanStep", sid, s.get("agent", "planner"), "s1", {"order": s["order"], "tick": s["tick"], "text": s["text"]})
        _influenced_by(g, sid, s["reads"], s["tick"], "s1")
        done(sid)

    for aid, a in fx["artifacts"].items():
        _memory(g, "Artifact", aid, a.get("agent", "coder"), "s1", {"path": a["path"], "tick": a["tick"], "text": a["text"]})
        _influenced_by(g, aid, a["reads"], a["tick"], "s1")
        done(aid)


def derive_rework(g: Graph, memory_id: str) -> dict:
    """Rework spec for any quarantined step/artifact, computed from the graph (no scripted fixture needed):
    keep each clean read, swap a quarantined read for its healed twin, drop a quarantined read that has no
    twin (it can never heal). The text is the old text marked as reworked."""
    rows = q(g, """
        MATCH (m:Memory {id: $id})
        OPTIONAL MATCH (m)-[:INFLUENCED_BY]->(x:Memory)
        OPTIONAL MATCH (x)<-[:SUPERSEDES]-(t:Memory {quarantined: false})
        RETURN m.text, x.id, x.quarantined, t.id
    """, id=memory_id)
    text = rows[0][0] if rows else ""
    reads = []
    for _, xid, xq, tid in rows:
        if xid is None:
            continue
        if not xq:
            reads.append(xid)
        elif tid:
            reads.append(tid)
    return {"text": f"{text} [reworked from clean sources]", "reads": sorted(set(reads))}


def rework(g: Graph, old_id: str, by: str, text: str, reads: list[str], tick: int, session: str, task: str | None = None) -> str:
    """An agent's rework write: a new memory of the same kind that SUPERSEDES the
    quarantined one, with its own read set. Refuses a read set that still cites
    quarantined, unreplaced memory (the harness guard that stops re-poisoning).
    Ensures caller is authorized author and holds active lease if task was claimed."""
    new_id = f"{old_id}_v2"

    # 1. Author and lease fencing check
    task_id = task or f"rework_{old_id}"
    task_rows = q(g, """
        OPTIONAL MATCH (old:Memory {id: $old})<-[:AUTHORED]-(orig_author:Agent)
        OPTIONAL MATCH (t:Task {id: $task})
        OPTIONAL MATCH (t)-[c:CLAIMED_BY]->(holder:Agent)
        RETURN orig_author.name, t.state, c.session, c.lease_until, holder.name
    """, old=old_id, task=task_id)

    if task_rows and task_rows[0][0] is not None:
        orig_author, t_state, c_session, c_lease_until, h_name = task_rows[0]
        if orig_author != by:
            raise ValueError(f"Unauthorized rework: agent {by!r} is not the author of {old_id}")
        if c_session is not None:
            if c_session != session or h_name != by:
                raise ValueError(f"Zombie or unauthorized write: task {task_id} is claimed by {h_name} in session {c_session}")
            if c_lease_until is not None and c_lease_until < tick:
                raise ValueError(f"Lease expired: task {task_id} lease expired at tick {c_lease_until} (current {tick})")

    # 2. Validate read set
    rows = q(g, "UNWIND $reads AS rid OPTIONAL MATCH (x:Memory {id: rid}) RETURN rid, x.quarantined", reads=reads)
    bad = [rid for rid, quarantined in rows if quarantined is None or quarantined]
    if bad:
        raise ValueError(f"read set cites missing or quarantined memory: {bad}")

    # 3. Idempotent check: if replacement already exists, check that it has complete provenance
    existing = q(g, "MATCH (m:Memory {id: $new}) RETURN m.id", new=new_id)
    if existing:
        current_reads = set(r[0] for r in q(g, "MATCH (m:Memory {id: $new})-[:INFLUENCED_BY]->(x) RETURN x.id", new=new_id))
        if current_reads == set(reads):
            return new_id
        # Incomplete provenance from interrupted write; remove incomplete node and recreate atomically
        q(g, "MATCH (m:Memory {id: $new}) DETACH DELETE m", new=new_id)

    # 4. Atomic write: create replacement node, SUPERSEDES, AUTHORED, RAN_IN, and all INFLUENCED_BY edges in one query
    kind_rows = q(g, "MATCH (m:Memory {id: $id}) RETURN labels(m)[1]", id=old_id)
    if not kind_rows:
        raise ValueError(f"Original memory {old_id} not found")
    kind = kind_rows[0][0]

    head = f"""
    MATCH (old:Memory {{id: $old}}), (a:Agent {{name: $by}})
    MERGE (s:Session {{id: $session}})
    CREATE (m:Memory:{kind} {{id: $new, tick: $tick, text: $text, quarantined: false, reworked_from: $old,
                             ungrounded: $ungrounded}})
    SET m.order = old.order, m.path = old.path
    CREATE (m)-[:SUPERSEDES]->(old), (a)-[:AUTHORED]->(m), (m)-[:RAN_IN]->(s)
    """
    if reads:
        cypher = head + """
    WITH m
    UNWIND $reads AS rid
    MATCH (x:Memory {id: rid})
    CREATE (m)-[:INFLUENCED_BY {read_tick: $tick, session: $session}]->(x)
    RETURN DISTINCT m.id
    """
    else:
        # Every input of the old memory was poisoned beyond repair: the agent redoes it from its task alone.
        # One statement (no UNWIND over nothing), and the twin is marked ungrounded so nobody mistakes it for sourced work.
        cypher = head + "RETURN m.id"
    res = q(g, cypher, old=old_id, by=by, session=session, new=new_id, tick=tick, text=text, reads=reads,
            ungrounded=not reads)
    if not res:
        raise RuntimeError(f"Atomic rework write failed for {new_id}")
    return new_id
