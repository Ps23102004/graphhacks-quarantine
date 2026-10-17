"""Load fixture.yaml into a FalkorDB graph and write scripted Session 2 rework.

The loader is the only place that knows the YAML shape. Everything the demo
does afterwards is a named statement in queries.py.
"""
from __future__ import annotations

import math
import os
import re
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
        if not p.exists() and not p.is_absolute():                      # `fixtures/x.yaml` from an installed wheel or the image
            for base in (FIXTURE_CHECKOUT.parent, Path(sys.prefix) / "share" / "quarantine"):
                if (base / p).exists():
                    p = base / p
                    break
    elif FIXTURE_CHECKOUT.exists():
        p = FIXTURE_CHECKOUT
    elif FIXTURE_INSTALLED.exists():
        p = FIXTURE_INSTALLED
    else:
        p = FIXTURE_CHECKOUT
    try:
        fx = yaml.load(p.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)   # noqa: S506  (a SafeLoader subclass)
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"cannot read fixture {p}: {e}") from None
    except yaml.YAMLError as e:
        raise ValueError(f"fixture {p} is not valid YAML: {str(e).splitlines()[0]}") from None
    if not isinstance(fx, dict):
        raise ValueError(f"fixture {p} must be a mapping of sections, got {type(fx).__name__}")
    return fx


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses a key repeated inside one mapping (plain YAML keeps the last one silently,
    which would let a second `ep_2:` replace a clean episode without any error)."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep)


TWIN_SUFFIX = re.compile(r"_v\d+$")                      # healed and reworked twins are named <id>_v2
RESERVED = {"Doc": ("id", "flagged", "flag_reason", "flag_tick"), "Agent": ("name",), "Session": ("id",)}
REQUIRED = {"episodes": (("doc", str), ("tick", int), ("text", str)),
            "facts": (("subject", str), ("slot", str), ("value", str), ("tick", int), ("support", list)),
            "steps": (("order", int), ("tick", int), ("text", str), ("reads", list)),
            "artifacts": (("path", str), ("tick", int), ("text", str), ("reads", list))}
DEFAULT_AGENT = {"episodes": "research", "facts": "research", "steps": "planner", "artifacts": "coder"}


def validate_fixture(fx: dict) -> None:
    """Validate fixture structure, references, and temporal monotone properties. Everything load() relies on is
    checked here, so a bad world is refused before the CLI deletes or writes anything."""
    if not isinstance(fx, dict):
        raise ValueError("fixture must be a mapping of sections")
    required = ("sessions", "agents", "docs", "episodes", "facts", "steps", "artifacts")
    for sec in required:
        if sec not in fx or not isinstance(fx[sec], dict):
            raise ValueError(f"Fixture missing required dictionary section: {sec!r}")
    if "s1" not in fx["sessions"]:
        raise ValueError("Fixture sessions must include 's1' (Session 1 writes every memory)")
    for sec, label in (("sessions", "Session"), ("agents", "Agent"), ("docs", "Doc")):
        for key, props in fx[sec].items():
            if not isinstance(props, dict):
                raise ValueError(f"{label} {key!r} must be a mapping")
            clash = [k for k in RESERVED[label] if k in props]
            if clash:
                raise ValueError(f"{label} {key!r} sets reserved key(s) {clash}; they are written by the harness")
    for sec, fields in REQUIRED.items():
        for mid, m in fx[sec].items():
            if not isinstance(mid, str) or not mid:
                raise ValueError(f"{sec}: memory id {mid!r} must be a non-empty string")
            if TWIN_SUFFIX.search(mid):
                raise ValueError(f"{sec}: id {mid!r} ends in the reserved suffix _v<n> used for healed and reworked twins")
            if not isinstance(m, dict):
                raise ValueError(f"{sec}: {mid!r} must be a mapping")
            unknown = set(m) - {f for f, _ in fields} - {"agent", "note"}
            if unknown:
                # e.g. `reads:` on a fact or episode would be silently dropped, hiding provenance: refuse instead
                raise ValueError(f"{sec}: {mid!r} has unknown key(s) {sorted(unknown)}; only {[f for f, _ in fields]} "
                                 f"(+ agent, note) are read, so anything else would be ignored")
            for field_name, typ in fields:
                if not isinstance(m.get(field_name), typ) or isinstance(m.get(field_name), bool):
                    raise ValueError(f"{sec}: {mid!r} needs {field_name!r} as {typ.__name__}, got {m.get(field_name)!r}")
            agent = m.get("agent", DEFAULT_AGENT[sec])
            if agent not in fx["agents"]:
                raise ValueError(f"{sec}: {mid!r} names unknown agent {agent!r}")
        if sec == "facts":
            for fid, f in fx["facts"].items():
                for s in f["support"]:
                    if not isinstance(s, dict) or not isinstance(s.get("ep"), str) or not isinstance(s.get("claim"), str):
                        raise ValueError(f"facts: {fid!r} support entries need 'ep' and 'claim' strings, got {s!r}")
                eps = [s["ep"] for s in f["support"]]
                if len(eps) != len(set(eps)):
                    raise ValueError(f"facts: {fid!r} lists the same episode twice in its support (one episode is one vote)")
        if sec in ("steps", "artifacts"):
            for mid, m in fx[sec].items():
                if not all(isinstance(r, str) for r in m["reads"]):
                    raise ValueError(f"{sec}: {mid!r} reads must be memory ids, got {m['reads']!r}")

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
    """Local to live by environment only (organizers' guide): FALKORDB_HOST/PORT for the Docker image,
    plus FALKORDB_USERNAME/FALKORDB_PASSWORD and FALKORDB_TLS=1 for FalkorDB Cloud. Same code either way."""
    return FalkorDB(**connection_kwargs(host, port)).select_graph(name)


def connection_kwargs(host: str | None = None, port: int | None = None) -> dict:
    kw: dict = {"host": host if host is not None else os.environ.get("FALKORDB_HOST", "localhost"),
                "port": port if port is not None else int(os.environ.get("FALKORDB_PORT", 6379))}
    if os.environ.get("FALKORDB_USERNAME"):
        kw["username"] = os.environ["FALKORDB_USERNAME"]
    if os.environ.get("FALKORDB_PASSWORD"):
        kw["password"] = os.environ["FALKORDB_PASSWORD"]
    if os.environ.get("FALKORDB_TLS", "").lower() in ("1", "true", "yes"):
        kw["ssl"] = True
    return kw


def q(g: Graph, cypher: str, **params):
    """Run one write-capable statement, return result rows."""
    return g.query(cypher, params).result_set


def rq(g: Graph, cypher: str, **params):
    """Run one read-only statement through GRAPH.RO_QUERY, return result rows. No write-path fallback."""
    return g.ro_query(cypher, params).result_set


def _node(g: Graph, labels: str, props: dict) -> None:
    res = q(g, f"CREATE (n:{labels}) SET n += $p RETURN count(n)", p=props)
    if not res or res[0][0] == 0:
        raise RuntimeError(f"Failed to create node :{labels} with props {props}")


def _memory(g: Graph, labels: str, mid: str, author: str, session: str, props: dict,
            edge: str | None = None, target: str = "Memory", links: list[dict] | None = None) -> None:
    """One memory, its authorship and its provenance edges in ONE statement, so a crash can never leave a memory
    without the read set it was written from. links: [{id, props}] targets of `edge`."""
    links = links or []
    cypher = (f"MATCH (a:Agent {{name: $author}}), (s:Session {{id: $session}}) "
              f"CREATE (m:Memory:{labels}) SET m += $p, m.id = $mid, m.quarantined = false "
              f"CREATE (a)-[:AUTHORED]->(m), (m)-[:RAN_IN]->(s) ")
    if links:
        cypher += (f"WITH m UNWIND $links AS l MATCH (x:{target} {{id: l.id}}) "
                   f"CREATE (m)-[r:{edge}]->(x) SET r += l.props RETURN count(r)")
    else:
        cypher += "RETURN count(m)"
    res = q(g, cypher, author=author, session=session, p=props, mid=mid, links=links)
    if not res or res[0][0] != (len(links) or 1):
        raise RuntimeError(f"Failed to write memory {mid} by {author} with {len(links)} {edge or 'provenance'} edge(s)")


def _influenced_by(g: Graph, mid: str, reads: list[str], tick: int, session: str) -> None:
    """Add read edges to an existing memory (tests build worlds edge by edge; load() writes them with the memory)."""
    for rid in reads:
        res = q(g, "MATCH (m:Memory {id: $mid}), (x:Memory {id: $rid}) "
                   "CREATE (m)-[:INFLUENCED_BY {read_tick: $tick, session: $session}]->(x) "
                   "RETURN count(*)",
                mid=mid, rid=rid, tick=tick, session=session)
        if not res or res[0][0] == 0:
            raise ValueError(f"Failed to link INFLUENCED_BY from {mid} to missing {rid}")


# The crew's procedural memory: how an advisory is handled. Stored as a node every incident's tasks point at
# (Task)-[:FOLLOWS]->(Procedure), so "how we recover" is shared, versioned graph state, not a constant in code.
# The harness reads lease_ticks from it (cli.session2). The Memory label is reserved for per-write memories.
DEFAULT_PROCEDURE = {
    "id": "rework_procedure", "version": 1, "lease_ticks": 5, "heal_min_clean": 2,
    "steps": ["flag the document", "quarantine its provenance closure", "count clean support per fact",
              "one rework task per quarantined step or artifact, BLOCKED_BY its healable inputs",
              "heal facts by strict plurality of clean episodes", "promote tasks whose blockers are replaced",
              "author claims with an expiring lease", "rework from clean inputs only", "complete; repeat to a fixpoint"],
}


def write_procedure(g: Graph, proc: dict | None = None) -> None:
    p = {**DEFAULT_PROCEDURE, **(proc or {})}
    q(g, "MERGE (h:Agent {name: 'harness'}) ON CREATE SET h.role = 'harness' "
         "MERGE (p:Procedure {id: $id}) SET p += $props "
         "MERGE (h)-[:AUTHORED]->(p)", id=p["id"], props=p)


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
    write_procedure(g, fx.get("procedure"))

    for eid, e in fx["episodes"].items():
        _memory(g, "Episode", eid, e.get("agent", "research"), "s1", {"tick": e["tick"], "text": e["text"]},
                "EXTRACTED_FROM", "Doc", [{"id": e["doc"], "props": {}}])
        done(eid)

    for fid, f in fx["facts"].items():
        _memory(g, "Fact", fid, f.get("agent", "research"), "s1",
                {"subject": f["subject"], "slot": f["slot"], "value": f["value"],
                 "tick": f["tick"], "support_total": len(f["support"])},
                "CONSOLIDATED_FROM", "Episode", [{"id": s["ep"], "props": {"claim": s["claim"]}} for s in f["support"]])
        done(fid)

    for kind, label, agent, extra in (("steps", "PlanStep", "planner", "order"), ("artifacts", "Artifact", "coder", "path")):
        for mid, m in fx[kind].items():
            _memory(g, label, mid, m.get("agent", agent), "s1", {extra: m[extra], "tick": m["tick"], "text": m["text"]},
                    "INFLUENCED_BY", "Memory", [{"id": r, "props": {"read_tick": m["tick"], "session": "s1"}} for r in m["reads"]])
            done(mid)
    # the last write: Session 1 finished. `flag` refuses a graph without it (a crash mid-load is visible, not silent)
    q(g, "MATCH (s:Session {id: 's1'}) SET s.complete = true")


def reconcile(g: Graph) -> list[str]:
    """Re-derive quarantine, support and rework tasks from the documents that are flagged right now. Idempotent;
    run at the start of flag, unflag and session2 so any torn write from a crash is repaired before work continues."""
    from quarantine import queries as Q

    q(g, Q.DROP_UNFLAGGED_CAUSE)
    flagged = q(g, Q.STILL_FLAGGED)
    for d, tick in flagged:
        q(g, Q.TAINT_CLOSURE, doc=d, tick=tick if tick is not None else 0)
    q(g, Q.CLEAR_STALE)
    q(g, Q.DELETE_STALE_TASKS)
    q(g, Q.SUPPORT_AND_HEALABLE)
    if flagged:
        q(g, Q.CREATE_REWORK_TASKS, tick=max((t or 0) for _, t in flagged))
    q(g, Q.CREATE_BLOCKED_BY)
    return [d for d, _ in flagged]


def derive_rework(g: Graph, memory_id: str) -> dict:
    """Rework spec for any quarantined step/artifact, computed from the graph (no scripted fixture needed):
    keep each clean read, swap a quarantined read for its healed twin, drop a quarantined read that has no
    twin (it can never heal).

    The harness cannot author content, and it must NOT copy the quarantined memory's text into a memory that
    is then trusted as clean (that would launder the poison). So the twin carries a placeholder that names
    the clean inputs and is flagged needs_regeneration: a real agent (or the scripted fixture) supplies the
    text. See rework(): any `text` it is given is what gets stored."""
    rows = q(g, """
        MATCH (m:Memory {id: $id})
        OPTIONAL MATCH (m)-[:INFLUENCED_BY]->(x:Memory)
        OPTIONAL MATCH (x)<-[:SUPERSEDES]-(t:Memory {quarantined: false})
        RETURN x.id, x.quarantined, t.id
    """, id=memory_id)
    reads = []
    for xid, xq, tid in rows:
        if xid is None:
            continue
        if not xq:
            reads.append(xid)
        elif tid:
            reads.append(tid)
    reads = sorted(set(reads))
    return {"text": f"[needs regeneration: rebuild {memory_id} from {', '.join(reads) or 'its task alone'}]",
            "reads": reads, "needs_regeneration": True}


def rework(g: Graph, old_id: str, by: str, text: str, reads: list[str], tick: int, session: str, task: str | None = None,
           needs_regeneration: bool = False) -> str:
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
    existing = q(g, "MATCH (m:Memory {id: $new}) OPTIONAL MATCH (m)-[s:SUPERSEDES]->(:Memory {id: $old}) "
                    "RETURN m.id, count(s)", new=new_id, old=old_id)
    if existing and not existing[0][1]:
        # never delete or reuse a memory this rework did not create (validate_fixture reserves the suffix; this guards
        # graphs written by anything else)
        raise ValueError(f"a memory named {new_id!r} already exists and is not a replacement of {old_id!r}")
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
                             ungrounded: $ungrounded, needs_regeneration: $regen}})
    SET m.order = old.order, m.path = old.path
    CREATE (m)-[:SUPERSEDES]->(old), (a)-[:AUTHORED]->(m), (m)-[:RAN_IN]->(s)
    WITH m
    OPTIONAL MATCH (t:Task {{id: $task}})
    FOREACH (tt IN CASE WHEN t IS NULL THEN [] ELSE [t] END | MERGE (m)-[:REWORKED_FOR]->(tt))
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
            ungrounded=not reads, regen=needs_regeneration, task=task_id)
    if not res:
        raise RuntimeError(f"Atomic rework write failed for {new_id}")
    return new_id


def unflag(g: Graph, doc: str) -> dict:
    """Retract an advisory (a false alarm), then reconcile: a memory stays red only if some document that is still
    flagged reaches it, and nothing a flagged document reaches is ever cleared, even for a moment. Refuses once healing
    has started: clean replacements already exist and would no longer match a rebuilt state (reset with session1)."""
    from quarantine import queries as Q

    if not q(g, "MATCH (d:Doc {id: $doc}) RETURN d.id", doc=doc):
        raise KeyError(f"no doc {doc!r} in the graph")
    replacements, started = q(g, Q.HEAL_STARTED)[0]
    if replacements or started:
        raise RuntimeError("healing has already started; un-flagging now would leave replacements without a cause "
                           "(run `quarantine session1` to reset the demo)")
    if not q(g, Q.UNFLAG_DOC, doc=doc):
        raise KeyError(f"{doc!r} is not flagged; nothing to retract")
    still = reconcile(g)
    red = [r[0] for r in q(g, "MATCH (m:Memory {quarantined: true}) RETURN m.id ORDER BY m.tick")]
    return {"still_flagged": still, "quarantined": red}
