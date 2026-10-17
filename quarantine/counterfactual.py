"""Evidence that does not share the specification: replay each world WITHOUT the poisoned document.

The held-out oracle (worldgen.py) restates the quarantine rule in Python, so it can only show the Cypher implements
the rule. This module asks whether the rule is right. It gives every memory a symbolic content (an episode is its
text, a fact is the plurality claim of its support, a step or artifact is its text plus the contents of what it read),
recomputes every content in the world with the flagged document removed, and calls a memory *truly affected* if its
content differs or it can no longer exist.

Two directions, very different in cost:
  - false negative: truly affected but left clean. Poison keeps being used. Must be zero.
  - needless flag:  quarantined but its content would not have changed (a fact the poisoned episode only dissented
                    on, and everything downstream of it). Costs rework; if the memory cannot heal it is lost.
Both are measured against the real graph, per (world, flagged document).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from quarantine import queries as Q
from quarantine.answers import blast_radius, why_quarantined
from quarantine.loader import connect, load, q
from quarantine.worldgen import make_world

KINDS = ("episodes", "facts", "steps", "artifacts")


def plurality(claims: list[str]) -> str | None:
    if not claims:
        return None
    ranked = Counter(claims).most_common()
    top = [c for c, n in ranked if n == ranked[0][1]]
    return min(top)                                                    # deterministic tie-break


def contents(world: dict, drop_doc: str | None = None) -> dict[str, object]:
    """Symbolic content of every memory that can exist in this world, optionally with one document never ingested."""
    out: dict[str, object] = {}
    for eid, e in world["episodes"].items():
        if e["doc"] != drop_doc:
            out[eid] = ("ep", e["doc"], e["text"])
    for fid, f in world["facts"].items():
        live = [s["claim"] for s in f["support"] if s["ep"] in out]
        if live:
            out[fid] = ("fact", plurality(live))
    later = sorted(((m["tick"], mid) for k in ("steps", "artifacts") for mid, m in world[k].items()))
    for _, mid in later:
        m = world["steps"].get(mid) or world["artifacts"][mid]
        out[mid] = ("write", m["text"], tuple(sorted((r, out[r]) for r in m["reads"] if r in out)))
    return out


def truly_affected(world: dict, doc: str) -> set[str]:
    base, without = contents(world), contents(world, drop_doc=doc)
    return {mid for mid, c in base.items() if without.get(mid) != c}


def provenance_edges(world: dict) -> set[tuple[str, str, str]]:
    """(reader, edge type, read) for every provenance edge the world declares."""
    e = set()
    for eid, ep in world["episodes"].items():
        e.add((eid, "EXTRACTED_FROM", ep["doc"]))
    for fid, f in world["facts"].items():
        e |= {(fid, "CONSOLIDATED_FROM", s["ep"]) for s in f["support"]}
    for k in ("steps", "artifacts"):
        for mid, m in world[k].items():
            e |= {(mid, "INFLUENCED_BY", r) for r in m["reads"]}
    return e


@dataclass
class Tally:
    runs: int = 0
    memories: int = 0
    affected: int = 0
    flagged: int = 0
    needless: int = 0
    needless_unhealable_facts: int = 0
    false_negatives: list = field(default_factory=list)
    bad_receipts: list = field(default_factory=list)
    bad_clean_answers: list = field(default_factory=list)
    page_mismatch: list = field(default_factory=list)
    needless_by_kind: Counter = field(default_factory=Counter)


def check_receipt(world: dict, edges: set, mid: str, doc: str, got: dict) -> str | None:
    """A receipt is only honest if every hop is an edge the world declares and the path ends at the flagged document."""
    if got.get("shape") != "path":
        return f"{mid}: quarantined but answered {got.get('shape')}"
    hops, via = got["hops"], got["via"]
    if hops[0] != mid or hops[-1] != doc or len(via) != len(hops) - 1:
        return f"{mid}: path does not run {mid} -> {doc}: {hops}"
    for a, t, b in zip(hops, via, hops[1:]):
        if (a, t, b) not in edges:
            return f"{mid}: invented hop {a} -[{t}]-> {b}"
    return None


def evaluate_counterfactual(g, world: dict, seed: int = 0, mode: str = "declared") -> Tally:
    from web.server import snapshot                                   # the page's own read path

    t = Tally()
    load(g, world)
    edges = provenance_edges(world)
    total = sum(len(world[k]) for k in KINDS)
    kind_of = {mid: k for k in KINDS for mid in world[k]}
    for doc in world["docs"]:
        for stmt in ("MATCH (m:Memory) WHERE m.id ENDS WITH '_v2' DETACH DELETE m",
                     "MATCH (m:Memory) SET m.quarantined = false REMOVE m.quarantine_tick, m.quarantine_doc, m.support_clean, m.healable",
                     "MATCH (d:Doc) SET d.flagged = false"):
            q(g, stmt)
        # before the flag: nothing may be red, anywhere the page or an agent can look
        assert not any(n["red"] for n in snapshot(g)["nodes"]), "red before any flag"

        q(g, Q.FLAG_DOC, doc=doc, reason="counterfactual", tick=900)
        _, ids = q(g, Q.TAINT_CLOSURE, doc=doc, tick=900)[0]
        flagged = set(ids)
        truth = truly_affected(world, doc)
        flags = {r[0]: r[2] for r in q(g, Q.SUPPORT_AND_HEALABLE)}

        t.runs += 1; t.memories += total; t.affected += len(truth); t.flagged += len(flagged)
        missed = truth - flagged
        if missed:
            t.false_negatives.append((seed, mode, doc, sorted(missed)))
        needless = flagged - truth
        t.needless += len(needless)
        for m in needless:
            t.needless_by_kind[kind_of[m]] += 1
            if kind_of[m] == "facts" and not flags.get(m):
                t.needless_unhealable_facts += 1

        # every receipt is verifiable against the declared edges; every clean memory is answered as clean
        for m in flagged:
            bad = check_receipt(world, edges, m, doc, why_quarantined(g, m))
            if bad:
                t.bad_receipts.append((seed, mode, doc, bad))
        for m in set(kind_of) - flagged:
            got = why_quarantined(g, m)
            if got["shape"] != "not_in_graph":
                t.bad_clean_answers.append((seed, mode, doc, m, got["shape"]))
        br = blast_radius(g, doc)
        members = set(br.get("members", []))
        if members != flagged:
            t.page_mismatch.append((seed, mode, doc, "blast_radius", sorted(members ^ flagged)))

        # the page's snapshot must show exactly the closure in red, and the counters must be the closure's size
        snap = snapshot(g)
        red = {n["id"] for n in snap["nodes"] if n["red"]}
        if red != flagged:
            t.page_mismatch.append((seed, mode, doc, "page red set", sorted(red ^ flagged)))
        if snap["counters"] and snap["counters"]["precise"] != len(flagged):
            t.page_mismatch.append((seed, mode, doc, "page counter", snap["counters"]["precise"], len(flagged)))
    return t


def merge(a: Tally, b: Tally) -> Tally:
    for f in ("runs", "memories", "affected", "flagged", "needless", "needless_unhealable_facts"):
        setattr(a, f, getattr(a, f) + getattr(b, f))
    for f in ("false_negatives", "bad_receipts", "bad_clean_answers", "page_mismatch"):
        getattr(a, f).extend(getattr(b, f))
    a.needless_by_kind.update(b.needless_by_kind)
    return a


def run(seeds, mode: str = "declared", deep: bool = False, graph: str = "counterfactual_scratch") -> Tally:
    total = Tally()
    for seed in seeds:
        g = connect(graph)
        try:
            g.delete()
        except Exception:  # noqa: BLE001
            pass
        g = connect(graph)
        merge(total, evaluate_counterfactual(g, make_world(seed, mode, deep), seed, mode))
    connect(graph).delete()
    return total
