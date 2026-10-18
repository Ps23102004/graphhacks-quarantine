"""End-to-end check on ten different worlds, through the real CLI (session1, flag, unflag, session2, status).

    uv run python scripts/ten_worlds.py            # prints one line per world, exit 1 on any failure

For every world and every document in it: flag it, the red set must equal the independent oracle; session2 must reach a
fixpoint with every task done and the three audit queries at 0; unflag must return the graph to zero red. Then two
documents flagged together must give the oracle's union. Worlds: the demo, the support crew, six generated crews of different
shapes, one wide fan-out and one dissent-heavy world built here.
"""
from __future__ import annotations

import contextlib
import io
import itertools
import sys
import tempfile
from pathlib import Path

import yaml

from quarantine import cli
from quarantine import queries as Q
from quarantine.agent_runtime import recovery_status
from quarantine.loader import connect, q, read_fixture
from quarantine.worldgen import make_chain_world, make_world, oracle_tainted

ROOT = Path(__file__).resolve().parent.parent
GRAPH = "tw_ten"


def wide_world() -> dict:
    """One document fans out into six episodes, one fact, eight steps and three artifacts."""
    w = {"sessions": {"s1": {"label": "wide"}}, "agents": {a: {"role": a} for a in ("research", "w0", "w1", "w2")},
         "docs": {f"d{i}": {"uri": f"u{i}", "title": f"d{i}"} for i in range(1, 5)},
         "episodes": {f"e{i}": {"doc": "d1" if i <= 6 else "d2", "tick": i, "text": f"e{i}"} for i in range(1, 9)},
         "facts": {"f": {"subject": "s", "slot": "x", "tick": 10, "value": "a",
                         "support": [{"ep": f"e{i}", "claim": "a"} for i in range(1, 9)]}},
         "steps": {f"s{i}": {"order": i, "tick": 11 + i, "text": f"s{i}", "agent": f"w{i % 3}", "reads": ["f"]} for i in range(1, 9)},
         "artifacts": {f"a{i}": {"path": f"a{i}.py", "tick": 30 + i, "text": f"a{i}", "agent": "w1",
                                 "reads": [f"s{i}", f"s{i + 1}"]} for i in range(1, 4)}}
    return w


def dissent_world() -> dict:
    """Facts voted on by differently spelled claims from several documents, two of them poisoned."""
    claims = ["Requests", "requests", "requests ", "reqeusts", "reqeusts", "httpx", "Requests"]
    w = {"sessions": {"s1": {"label": "dissent"}}, "agents": {a: {"role": a} for a in ("research", "planner", "coder")},
         "docs": {f"d{i}": {"uri": f"u{i}", "title": f"d{i}"} for i in range(1, 8)},
         "episodes": {f"e{i}": {"doc": f"d{i}", "tick": i, "text": f"e{i}"} for i in range(1, 8)},
         "facts": {"f1": {"subject": "s", "slot": "x", "tick": 10, "value": "requests",
                          "support": [{"ep": f"e{i + 1}", "claim": c} for i, c in enumerate(claims)]},
                   "f2": {"subject": "s", "slot": "y", "tick": 11, "value": "httpx",
                          "support": [{"ep": "e6", "claim": "httpx"}, {"ep": "e7", "claim": "httpx"}]}},
         "steps": {"s1": {"order": 1, "tick": 12, "text": "s1", "agent": "planner", "reads": ["f1"]},
                   "s2": {"order": 2, "tick": 13, "text": "s2", "agent": "planner", "reads": ["f2", "s1"]}},
         "artifacts": {"a1": {"path": "a.py", "tick": 14, "text": "a1", "agent": "coder", "reads": ["s1", "s2"]}}}
    return w


def worlds() -> list[tuple[str, dict]]:
    return [("demo", read_fixture(ROOT / "fixture.yaml")), ("support-crew", read_fixture(ROOT / "fixtures" / "support-crew.yaml")),
            ("gen declared 11", make_world(11)), ("gen cumulative 12", make_world(12, "cumulative")),
            ("gen deep 13", make_world(13, "declared", True)), ("gen declared 14", make_world(14)),
            ("gen cumulative deep 15", make_world(15, "cumulative", True)), ("chain 25", make_chain_world(25)),
            ("wide fan-out", wide_world()), ("dissent-heavy", dissent_world())]


def run(*argv) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cli.main(list(argv))
    return out.getvalue()


def red(g) -> set[str]:
    return {r[0] for r in q(g, "MATCH (m:Memory {quarantined: true}) RETURN m.id")}


def check_world(name: str, world: dict, tmp: Path) -> list[str]:
    bad: list[str] = []
    f = tmp / f"{abs(hash(name))}.yaml"
    f.write_text(yaml.safe_dump({k: v for k, v in world.items() if k not in ("expected", "rework", "flag")}))
    fx = str(f) if name not in ("demo", "support-crew") else str(ROOT / ("fixture.yaml" if name == "demo" else "fixtures/support-crew.yaml"))
    base = ["--fixture", fx, "--graph", GRAPH]
    docs = sorted(world["docs"])

    def fresh():
        run("session1", *base)
        return connect(GRAPH)

    for d in docs:
        g = fresh()
        run("flag", d, *base)
        want = oracle_tainted(world, d)
        if red(g) != want:
            bad.append(f"{d}: red {sorted(red(g) ^ want)} differs from the oracle")
            continue
        try:
            run("session2", *base)
        except SystemExit as e:
            bad.append(f"{d}: session2 exited: {e}")
            continue
        open_tasks = q(g, "MATCH (t:Task) WHERE t.state <> 'done' RETURN t.id")
        if open_tasks:
            bad.append(f"{d}: tasks not done {open_tasks}")
        for audit in (Q.AUDIT_NO_FORWARD_INFLUENCE, Q.AUDIT_CLEAN_NEVER_CITES_QUARANTINED, Q.AUDIT_CLOSURE_IS_CLOSED):
            if q(g, audit)[0][0]:
                bad.append(f"{d}: audit failed")
        warns = [w for w in recovery_status(g)["warnings"] if "placeholder" not in w and "regenerat" not in w]
        if warns:
            bad.append(f"{d}: status warns {warns}")
        g = fresh()
        run("flag", d, *base)
        run("unflag", d, *base)
        if red(g):
            bad.append(f"{d}: unflag left {sorted(red(g))} red")
    for a, b in list(itertools.combinations(docs, 2))[:6]:
        g = fresh()
        run("flag", a, *base)
        run("flag", b, *base)
        if red(g) != oracle_tainted(world, a) | oracle_tainted(world, b):
            bad.append(f"{a}+{b}: union differs from the oracle")
        try:
            run("session2", *base)
        except SystemExit as e:
            bad.append(f"{a}+{b}: session2 exited: {e}")
    connect(GRAPH).delete()
    return bad


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as t:
        for name, world in worlds():
            n_docs = len(world["docs"])
            bad = check_world(name, world, Path(t))
            failures += len(bad)
            print(f"{'FAIL' if bad else 'ok  '}  {name:<24} {n_docs} docs  " + ("" if not bad else "; ".join(bad[:3])), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
