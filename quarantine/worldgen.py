"""Held-out evaluation: random crews the demo never saw, and an independent oracle.

make_world(seed) returns a dict in the same shape as fixture.yaml (docs, episodes,
facts, steps, artifacts, agents, sessions), so loader.load() puts it in FalkorDB
unchanged. oracle_* compute what the graph SHOULD answer with plain Python sets,
sharing no code or query text with queries.py.

What this tests: that the Cypher implements the stated rules on worlds nobody
tuned numbers for. What it does not test: whether captured read sets match what a
real agent was influenced by (see read_mode "cumulative" for the pessimistic case).
"""
from __future__ import annotations

import random
from collections import Counter

CLAIMS = ("x", "y", "z")


def make_world(seed: int, read_mode: str = "declared", deep: bool = False) -> dict:
    """read_mode: "declared" = each write reads only what it lists (the demo's model);
    "cumulative" = each step/artifact also counts everything its author read or wrote before
    (the pessimistic model: an agent's whole context influences every later write).
    deep=True chains steps so the provenance path is longer than the closure's hop bound."""
    r = random.Random(seed)
    n_docs = r.randint(6, 12)
    docs = {f"doc_{i}": {"uri": f"u/{i}", "title": f"doc {i}"} for i in range(1, n_docs + 1)}
    workers = [f"w{i}" for i in range(r.randint(2, 4))]
    agents = {"research": {"role": "research"}, **{w: {"role": "worker"} for w in workers}}

    tick = 0
    episodes: dict[str, dict] = {}
    for d in docs:
        for k in range(r.randint(1, 2)):
            tick += 1
            episodes[f"ep_{d[4:]}_{k}"] = {"doc": d, "tick": tick, "text": f"claim from {d}"}

    facts: dict[str, dict] = {}
    ep_ids = list(episodes)
    for i in range(r.randint(4, 8)):
        tick += 1
        k = r.randint(1, min(5, len(ep_ids)))
        majority = r.choice(CLAIMS)
        support = [{"ep": e, "claim": majority if r.random() < 0.7 else r.choice(CLAIMS)}
                   for e in r.sample(ep_ids, k)]
        facts[f"f_{i}"] = {"subject": "s", "slot": f"slot{i}", "tick": tick, "value": majority, "support": support}

    steps: dict[str, dict] = {}
    n_steps = r.randint(12, 16) if deep else r.randint(3, 7)
    for i in range(n_steps):
        tick += 1
        pool = list(facts) + list(steps)
        reads = [list(steps)[-1]] if (deep and steps) else []
        reads += r.sample(pool, r.randint(1, min(3, len(pool))))
        steps[f"step_{i}"] = {"order": i, "tick": tick, "text": f"step {i}", "agent": r.choice(workers),
                              "reads": sorted(set(reads))}

    artifacts: dict[str, dict] = {}
    for i in range(r.randint(2, 5)):
        tick += 1
        pool = list(steps) + list(facts) + list(artifacts)
        artifacts[f"art_{i}"] = {"path": f"f{i}.py", "tick": tick, "text": f"artifact {i}", "agent": r.choice(workers),
                                 "reads": sorted(set(r.sample(pool, r.randint(1, min(3, len(pool))))))}

    world = {"sessions": {"s1": {"label": "held-out"}}, "agents": agents, "docs": docs,
             "episodes": episodes, "facts": facts, "steps": steps, "artifacts": artifacts}
    if read_mode == "cumulative":
        _make_cumulative(world)
    return world


def _make_cumulative(world: dict) -> None:
    """Each step/artifact also reads everything its author read or wrote earlier (pessimistic influence)."""
    seen: dict[str, set[str]] = {}
    writes = [(w["tick"], mid, w) for kind in ("steps", "artifacts") for mid, w in world[kind].items()]
    for _, mid, w in sorted(writes):
        ctx = seen.setdefault(w["agent"], set())
        w["reads"] = sorted(set(w["reads"]) | (ctx - {mid}))
        ctx |= {mid} | set(w["reads"])


# ------------------------------------------------------------------ oracle (plain Python, no graph)
def _author(world: dict, mid: str) -> str:
    for kind in ("episodes", "facts", "steps", "artifacts"):
        if mid in world[kind]:
            return world[kind][mid].get("agent", "research" if kind in ("episodes", "facts") else "?")
    raise KeyError(mid)


def _memories(world: dict) -> dict[str, int]:
    return {mid: m["tick"] for kind in ("episodes", "facts", "steps", "artifacts") for mid, m in world[kind].items()}


def oracle_tainted(world: dict, doc: str) -> set[str]:
    """Fixpoint, not traversal: a memory is tainted if it was extracted from the doc, consolidated from
    a tainted episode, or read a tainted memory. Repeat until nothing changes."""
    tainted = {e for e, v in world["episodes"].items() if v["doc"] == doc}
    changed = True
    while changed:
        changed = False
        for fid, f in world["facts"].items():
            if fid not in tainted and any(s["ep"] in tainted for s in f["support"]):
                tainted.add(fid); changed = True
        for kind in ("steps", "artifacts"):
            for mid, m in world[kind].items():
                if mid not in tainted and any(x in tainted for x in m["reads"]):
                    tainted.add(mid); changed = True
    return tainted


def oracle_baselines(world: dict, doc: str, tainted: set[str]) -> tuple[int, int]:
    """(wipe every agent that authored a tainted memory, forget everything written at or after the doc's first episode)"""
    mem = _memories(world)
    bad_agents = {_author(world, m) for m in tainted}
    per_agent = sum(1 for m in mem if _author(world, m) in bad_agents)
    firsts = [v["tick"] for v in world["episodes"].values() if v["doc"] == doc]
    time_based = sum(1 for t in mem.values() if firsts and t >= min(firsts))
    return per_agent, time_based


def oracle_heal(world: dict, tainted: set[str]) -> dict[str, tuple[str, int]]:
    """For each tainted fact: if its clean episodes have a strict plurality claim backed by >= 2 episodes,
    it heals to that claim. Returns {fact_id: (claim, agreeing_episode_count)}."""
    out = {}
    for fid, f in world["facts"].items():
        if fid not in tainted:
            continue
        counts = Counter(s["claim"] for s in f["support"] if s["ep"] not in tainted).most_common()
        if counts and counts[0][1] >= 2 and (len(counts) == 1 or counts[0][1] > counts[1][1]):
            out[fid] = counts[0]
    return out


def make_chain_world(n_steps: int) -> dict:
    """One poisoned doc feeding a single chain: doc -> episode -> fact -> step_0 -> step_1 -> ... -> step_{n-1} -> artifact.
    Every memory is reachable only through the full chain, so any hop bound shows up as missed memories."""
    steps = {}
    for i in range(n_steps):
        steps[f"step_{i}"] = {"order": i, "tick": 10 + i, "text": f"s{i}", "agent": "w0",
                              "reads": ["f_0"] if i == 0 else [f"step_{i - 1}"]}
    return {"sessions": {"s1": {"label": "chain"}}, "agents": {"research": {"role": "r"}, "w0": {"role": "w"}},
            "docs": {"doc_1": {"uri": "u", "title": "t"}, "doc_2": {"uri": "u2", "title": "t2"}},
            "episodes": {"ep_1": {"doc": "doc_1", "tick": 1, "text": "bad"}, "ep_2": {"doc": "doc_2", "tick": 2, "text": "ok"}},
            "facts": {"f_0": {"subject": "s", "slot": "x", "tick": 5, "value": "x",
                              "support": [{"ep": "ep_1", "claim": "x"}, {"ep": "ep_2", "claim": "x"}]}},
            "steps": steps,
            "artifacts": {"art_0": {"path": "a.py", "tick": 10 + n_steps, "text": "a", "agent": "w0",
                                    "reads": [f"step_{n_steps - 1}"]}}}
