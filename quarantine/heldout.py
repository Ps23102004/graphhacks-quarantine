"""Run the real queries on worlds the demo never saw and compare with the independent oracle."""
from __future__ import annotations

from dataclasses import dataclass, field

from quarantine import queries as Q
from quarantine.loader import connect, load, q
from quarantine.worldgen import make_world, oracle_baselines, oracle_heal, oracle_tainted

RESET = [
    "MATCH (m:Memory) WHERE m.id ENDS WITH '_v2' DETACH DELETE m",
    "MATCH (m:Memory) SET m.quarantined = false REMOVE m.quarantine_tick, m.support_clean, m.healable",
    "MATCH (d:Doc) SET d.flagged = false",
]


@dataclass
class Case:
    seed: int
    mode: str
    doc: str
    total: int
    precise: int
    per_agent: int
    time_based: int
    mismatches: list[str] = field(default_factory=list)


def evaluate_world(g, world: dict, seed: int = 0, mode: str = "declared") -> list[Case]:
    """Flag every doc of the world in turn; the graph's answer must equal the oracle's, exactly."""
    load(g, world)
    total = sum(len(world[k]) for k in ("episodes", "facts", "steps", "artifacts"))
    cases = []
    for doc in world["docs"]:
        for stmt in RESET:
            q(g, stmt)
        want = oracle_tainted(world, doc)
        want_pa, want_time = oracle_baselines(world, doc, want)
        want_heal = oracle_heal(world, want)

        q(g, Q.FLAG_DOC, doc=doc, reason="held-out", tick=900)
        precise, got_ids = q(g, Q.TAINT_CLOSURE, doc=doc, tick=900)[0]
        got = set(got_ids)
        pa = q(g, Q.NAIVE_PER_AGENT, doc=doc)[0][0]
        tb = q(g, Q.NAIVE_TIME_BASED, doc=doc)[0][0]
        flags = {r[0]: r[2] for r in q(g, Q.SUPPORT_AND_HEALABLE)}
        healed = {r[0].removesuffix("_v2"): (r[1], r[2]) for r in q(g, Q.HEAL_FACTS, session="s2", tick=901)}

        c = Case(seed, mode, doc, total, len(got), pa, tb)
        if got != want:
            c.mismatches.append(f"closure: graph-only {sorted(got - want)} oracle-only {sorted(want - got)}")
        if pa != want_pa:
            c.mismatches.append(f"per-agent baseline: graph {pa} oracle {want_pa}")
        if tb != want_time:
            c.mismatches.append(f"time baseline: graph {tb} oracle {want_time}")
        want_flags = {m: (m in want_heal) for m in want if m in world["facts"]}
        got_flags = {m: bool(flags.get(m)) for m in want if m in world["facts"]}
        if got_flags != want_flags:
            c.mismatches.append(f"healable flags: graph {got_flags} oracle {want_flags}")
        if healed != want_heal:
            c.mismatches.append(f"heal: graph {healed} oracle {want_heal}")
        cases.append(c)
    return cases


def run(seeds, mode: str = "declared", deep: bool = False, graph: str = "heldout_scratch") -> list[Case]:
    out: list[Case] = []
    for seed in seeds:
        g = connect(graph)
        try:
            g.delete()
        except Exception:  # noqa: BLE001  (graph did not exist)
            pass
        g = connect(graph)
        out += evaluate_world(g, make_world(seed, mode, deep), seed, mode)
    connect(graph).delete()
    return out


def summarize(cases: list[Case]) -> dict:
    live = [c for c in cases if c.precise > 0]
    clean = lambda c, n: (n - c.precise) / (c.total - c.precise) if c.total > c.precise else 0.0  # noqa: E731
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0  # noqa: E731
    return dict(
        cases=len(cases), mismatched=sum(1 for c in cases if c.mismatches), with_taint=len(live),
        mean_precise_frac=mean([c.precise / c.total for c in live]),
        mean_per_agent_frac=mean([c.per_agent / c.total for c in live]),
        mean_time_frac=mean([c.time_based / c.total for c in live]),
        clean_lost_per_agent=mean([clean(c, c.per_agent) for c in live]),
        clean_lost_time=mean([clean(c, c.time_based) for c in live]),
    )
