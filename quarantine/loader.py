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
            if key_node.tag == "tag:yaml.org,2002:merge":           # `<<: *anchor`: SafeLoader merges it below; an
                continue                                           # explicit key may override a merged one, as in YAML
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError:
                raise yaml.constructor.ConstructorError(None, None, "found unhashable key", key_node.start_mark) from None
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep)


TWIN_SUFFIX = re.compile(r"_v\d+$")                      # healed and reworked twins are named <id>_v2
RESERVED = {"Doc": ("id", "flagged", "flag_reason", "flag_tick"), "Agent": ("name",), "Session": ("id", "complete")}
INT64 = (-2 ** 63, 2 ** 63 - 1)                           # FalkorDB integers
MAX_ID = 256                                              # answers.valid_id: a longer id could never be explained
MAX_TICK = 2 ** 53                                        # room for session2 to count on without overflowing int64
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
    _check_values(fx, "fixture")
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
            _check_id(key, label)
            clash = [k for k in RESERVED[label] if k in props]
            if clash:
                raise ValueError(f"{label} {key!r} sets reserved key(s) {clash}; they are written by the harness")
            _check_props(props, f"{label} {key!r}")
    for sec, fields in REQUIRED.items():
        for mid, m in fx[sec].items():
            _check_id(mid, f"{sec}: memory")
            if TWIN_SUFFIX.search(mid):
                raise ValueError(f"{sec}: id {mid!r} ends in the reserved suffix _v<n> used for healed and reworked twins")
            if not isinstance(m, dict):
                raise ValueError(f"{sec}: {mid!r} must be a mapping")
            unknown = set(m) - {f for f, _ in fields} - {"agent", "note"}
            if unknown:
                # e.g. `reads:` on a fact or episode would be silently dropped, hiding provenance: refuse instead
                raise ValueError(f"{sec}: {mid!r} has unknown key(s) {sorted(unknown)}; only {[f for f, _ in fields]} "
                                 f"(+ agent) are read, and note is accepted as a comment and not stored, so anything "
                                 f"else would be ignored")
            for field_name, typ in fields:
                if not isinstance(m.get(field_name), typ) or isinstance(m.get(field_name), bool):
                    raise ValueError(f"{sec}: {mid!r} needs {field_name!r} as {typ.__name__}, got {m.get(field_name)!r}")
            agent = m.get("agent", DEFAULT_AGENT[sec])
            if not isinstance(agent, str):
                raise ValueError(f"{sec}: {mid!r} needs 'agent' as str, got {agent!r}")
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
    for sec in REQUIRED:
        for mid, m in fx[sec].items():
            if mid in known_memories:
                raise ValueError(f"Duplicate memory ID: {mid!r}")
            if not 0 < m["tick"] <= MAX_TICK:
                raise ValueError(f"{sec}: {mid!r} has invalid tick: {m['tick']!r} (ticks run from 1 to 2**53)")
            known_memories[mid] = m["tick"]
    for eid, e in fx["episodes"].items():
        if e["doc"] not in known_docs:
            raise ValueError(f"Episode {eid} references unknown doc: {e['doc']!r}")
    for fid, f in fx["facts"].items():
        for s in f["support"]:
            if s["ep"] not in fx["episodes"]:
                raise ValueError(f"Fact {fid} references unknown episode: {s['ep']!r}")
            if known_memories[s["ep"]] >= f["tick"]:
                raise ValueError(f"Temporal violation: Fact {fid} (tick {f['tick']}) cites later episode {s['ep']}")
    # any memory may be read, in any section and listed in any order; load() writes reads before their readers
    for sec, label in (("steps", "Step"), ("artifacts", "Artifact")):
        for mid, m in fx[sec].items():
            for rid in m["reads"]:
                if rid not in known_memories:
                    raise ValueError(f"{label} {mid} references unknown memory in read set: {rid!r}")
                if known_memories[rid] >= m["tick"]:
                    raise ValueError(f"Temporal violation: {label} {mid} (tick {m['tick']}) cites later memory {rid}")
    _check_sections(fx, known_docs)


def _check_id(x, what: str) -> None:
    if not isinstance(x, str) or not x or len(x) > MAX_ID or "\x00" in x:
        raise ValueError(f"{what} id {x!r} must be a non-empty string of at most {MAX_ID} characters with no NUL")


def _check_values(x, where: str) -> None:
    """Every value anywhere in the fixture is one FalkorDB can store: a NUL-free UTF-8 string, an int64, a finite float,
    a bool, null, or a list or mapping (with non-empty string keys) of those."""
    if isinstance(x, dict):
        for k, v in x.items():
            if not isinstance(k, str) or not k or "\x00" in k:
                raise ValueError(f"{where}: key {k!r} must be a non-empty string with no NUL")
            _check_values(v, f"{where}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _check_values(v, f"{where}[{i}]")
    elif isinstance(x, str):
        if "\x00" in x:
            raise ValueError(f"{where}: strings may not contain NUL")
        try:
            x.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError(f"{where}: string is not valid UTF-8") from None
    elif isinstance(x, bool) or x is None:
        pass
    elif isinstance(x, int):
        if not INT64[0] <= x <= INT64[1]:
            raise ValueError(f"{where}: integer {x} does not fit in 64 bits")
    elif isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError(f"{where}: number {x} is not finite")
    else:
        raise ValueError(f"{where}: {type(x).__name__} values are not supported (quote dates and times as strings)")


def _check_props(props: dict, what: str) -> None:
    """Node properties: scalars or flat lists of scalars (FalkorDB stores no maps and no nested lists)."""
    for k, v in props.items():
        if isinstance(v, dict) or (isinstance(v, list) and any(isinstance(i, (dict, list)) or i is None for i in v)):
            raise ValueError(f"{what} property {k!r} must be a string, number, boolean or a flat list of those, got {v!r}")


def _positive_tick(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 < v <= MAX_TICK


def _check_sections(fx: dict, docs: set) -> None:
    """The optional sections flag, rework and procedure, which the CLI reads in flag and session2."""
    f = fx.get("flag")
    if f is not None:
        if not isinstance(f, dict):
            raise ValueError(f"flag must be a mapping {{doc, tick, reason}}, got {f!r}")
        if f.get("doc") not in docs:
            raise ValueError(f"flag: doc {f.get('doc')!r} is not one of the fixture's docs")
        if not _positive_tick(f.get("tick")):
            raise ValueError(f"flag: tick must be a positive integer, got {f.get('tick')!r}")
        if not isinstance(f.get("reason"), str):
            raise ValueError(f"flag: reason must be a string, got {f.get('reason')!r}")
    rw = fx.get("rework")
    if rw is not None:
        if not isinstance(rw, dict):
            raise ValueError(f"rework must be a mapping of memory id to {{text, reads}}, got {rw!r}")
        for mid, spec in rw.items():
            if not isinstance(spec, dict) or not isinstance(spec.get("text"), str):
                raise ValueError(f"rework: {mid!r} needs 'text' as str")
            if not isinstance(spec.get("reads"), list) or not all(isinstance(r, str) for r in spec["reads"]):
                raise ValueError(f"rework: {mid!r} needs 'reads' as a list of memory ids, got {spec.get('reads')!r}")
            if not isinstance(spec.get("needs_regeneration", False), bool):
                raise ValueError(f"rework: {mid!r} needs_regeneration must be true or false")
    proc = fx.get("procedure")
    if proc is not None:
        if not isinstance(proc, dict):
            raise ValueError(f"procedure must be a mapping, got {proc!r}")
        _check_props(proc, "procedure")
        if "lease_ticks" in proc and not _positive_tick(proc["lease_ticks"]):
            raise ValueError(f"procedure: lease_ticks must be a positive integer, got {proc['lease_ticks']!r}")
        if proc.get("id", DEFAULT_PROCEDURE["id"]) != DEFAULT_PROCEDURE["id"]:
            raise ValueError(f"procedure: id is {DEFAULT_PROCEDURE['id']!r} (the harness reads that node)")
        if proc.get("heal_min_clean", 2) != 2:
            raise ValueError("procedure: heal_min_clean is fixed at 2 (queries.HEAL_FACTS); another value would be untrue")


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

    rest = [(label, agent, extra, mid, m) for kind, label, agent, extra in
            (("steps", "PlanStep", "planner", "order"), ("artifacts", "Artifact", "coder", "path"))
            for mid, m in fx[kind].items()]
    seen = set(fx["episodes"]) | set(fx["facts"])
    for *_, mid, m in rest:
        if not seen.issuperset(m["reads"]):                       # listed before what it reads: write in tick order,
            rest.sort(key=lambda r: r[4]["tick"])                 # always valid since reads point at smaller ticks
            break
        seen.add(mid)
    for label, agent, extra, mid, m in rest:
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
    keep each clean read, swap a quarantined read for the clean head of its SUPERSEDES chain, drop a quarantined read that has no
    twin (it can never heal).

    The harness cannot author content, and it must NOT copy the quarantined memory's text into a memory that
    is then trusted as clean (that would launder the poison). So the twin carries a placeholder that names
    the clean inputs and is flagged needs_regeneration: a real agent (or the scripted fixture) supplies the
    text. See rework(): any `text` it is given is what gets stored."""
    rows = q(g, """
        MATCH (m:Memory {id: $id})
        OPTIONAL MATCH (m)-[:INFLUENCED_BY]->(x:Memory)
        OPTIONAL MATCH (x)<-[:SUPERSEDES*1..]-(t:Memory {quarantined: false})      // the chain's clean head
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
    red_ids = "MATCH (m:Memory {quarantined: true}) RETURN m.id ORDER BY m.tick"
    retracted = bool(q(g, Q.UNFLAG_DOC, doc=doc))                       # the retraction and its clearing: one write
    before = [r[0] for r in q(g, red_ids)]
    still = reconcile(g)
    red = [r[0] for r in q(g, red_ids)]
    repaired = [m for m in before if m not in red]                      # what reconcile had to clear: a torn state
    if not retracted and not repaired:
        raise KeyError(f"{doc!r} is not flagged; nothing to retract")
    out = {"still_flagged": still, "quarantined": red}
    if not retracted:                                                   # an earlier retraction was interrupted
        out["repaired"] = repaired                                      # before its memories were cleared
    return out
