"""The demo as three commands over one FalkorDB graph.

    quarantine session1 [--slow 0.4]      load Session 1 from fixture.yaml
    quarantine flag doc_7                 advisory lands: closure, baselines, receipts
    quarantine session2 [--kill-planner]  heal + rework to a fixpoint

Everything is the same statements tests/test_quarantine.py asserts; this file only prints them.
"""
from __future__ import annotations

import argparse
import sys
import time

from quarantine import queries as Q
from quarantine.loader import connect, load, q, read_fixture, rework

LEASE = 5
AGENTS = ("planner", "coder")


def say(line: str = "") -> None:
    print(line, flush=True)


def ids(xs) -> str:
    return "[" + ", ".join(xs) + "]"


def short(text: str, width: int = 48) -> str:
    return text if len(text) <= width else text[:width].rstrip() + " ..."


def must(rows, what: str):
    if not rows:
        sys.exit(f"error: {what}")
    return rows


def startup_line(agent: str, memory: str, task, state, waiting) -> str:
    return f"{agent}: {memory}  task {task or '-'}  {state or '-'}  waiting_on {ids(waiting)}"


# ---------------------------------------------------------------- session 1
def session1(args) -> None:
    fx = read_fixture()
    g = connect(args.graph)
    try:
        g.delete()
    except Exception:  # noqa: BLE001  (graph did not exist yet)
        pass
    g = connect(args.graph)
    # what each memory did, from the fixture; printed the moment the loader has written it
    did: dict[str, tuple[str, str, str, int]] = {}
    for k, e in fx["episodes"].items():
        did[k] = ("research", f"extracted {e['doc']}", e["text"], e["tick"])
    for k, f in fx["facts"].items():
        did[k] = ("research", f"consolidated {ids(s['ep'] for s in f['support'])}", f["value"], f["tick"])
    for kind, agent in (("steps", "planner"), ("artifacts", "coder")):
        for k, s_ in fx[kind].items():
            did[k] = (agent, f"read {ids(s_['reads'])}", s_["text"], s_["tick"])

    written = []

    def show(mid: str) -> None:
        agent, action, text, tick = did[mid]
        written.append(mid)
        say(f'tick {tick:>2}  {agent:<8}  {action} -> wrote {mid}  "{short(text)}"')
        if args.slow:
            time.sleep(args.slow)

    load(g, fx, after_write=show)
    rows = written
    say(f"{len(rows)} memories written")
    say("session 1 done - 0 processes running")


# ---------------------------------------------------------------- flag
def flag(args) -> None:
    fx = read_fixture()
    g = connect(args.graph)
    f = fx["flag"]
    reason = args.reason or (f["reason"] if args.doc == f["doc"] else f"flagged {args.doc} from the CLI")
    must(q(g, Q.FLAG_DOC, doc=args.doc, reason=reason, tick=f["tick"]),
         f"no doc {args.doc!r} in graph {args.graph!r} (run `quarantine session1` first)")
    say(f"flagged {args.doc}: {reason}")

    precise, closure_ids = q(g, Q.TAINT_CLOSURE, doc=args.doc, tick=f["tick"])[0]
    q(g, Q.SUPPORT_AND_HEALABLE)
    q(g, Q.CREATE_REWORK_TASKS, tick=f["tick"])
    blocked = q(g, Q.CREATE_BLOCKED_BY)
    naive, _ = q(g, Q.NAIVE_PER_AGENT, doc=args.doc)[0]
    naive_time, _ = q(g, Q.NAIVE_TIME_BASED, doc=args.doc)[0]

    say(f"precise {precise} | per-agent {naive} | time-based {naive_time}")
    closure = [r[0] for r in q(g, "MATCH (m:Memory {quarantined: true}) RETURN m.id ORDER BY m.tick")]
    say(f"closure {ids(closure)}")
    for task, waiting in blocked:
        say(f"task {task}  blocked_by {ids(waiting)}")
    for (aid,) in q(g, "MATCH (m:Artifact {quarantined: true}) RETURN m.id ORDER BY m.tick"):
        if aid not in closure_ids:
            continue                                                    # red from an earlier advisory
        hops, length, via = q(g, Q.RECEIPT, **{"from": aid, "doc": args.doc})[0]
        chain = hops[0] + "".join(f" -{t}-> {h}" for t, h in zip(via, hops[1:]))
        say(f"receipt {aid} ({length} hops): {chain}")


# ---------------------------------------------------------------- session 2
def kill_planner(g, task: str, tick: int) -> int:
    """Planner process s2 claims `task` and dies. Returns the tick at which a new process (s2b) holds the lease."""
    def claim(now: int, session: str):
        return q(g, Q.CLAIM, task=task, me="planner", now=now, lease=LEASE, session=session)

    must(claim(tick, "s2"), f"planner could not claim {task}")
    say(f"  planner claimed {task} (session s2, lease until tick {tick + LEASE}) ... killed (no COMPLETE)")
    for memory, _h, t, state, waiting in q(g, Q.STARTUP, me="coder"):
        say("  " + startup_line("coder", memory, t, state, waiting))

    live = tick + 2
    if claim(live, "s2b"):
        sys.exit("error: second planner claim succeeded while the lease was live")
    say(f"  planner (new process, session s2b): claim refused at tick {live}, lease live until tick {tick + LEASE}")

    tick += LEASE + 1
    (_, old), = must(claim(tick, "s2b"), "planner could not take over the expired lease")
    say(f"  planner (new process, session s2b) took over lease from {old}")
    return tick


def session2(args) -> None:
    fx = read_fixture()
    g = connect(args.graph)
    must(q(g, "MATCH (t:Task) RETURN t.id LIMIT 1"), "no rework tasks yet (run `quarantine flag DOC` first)")

    say("session 2: fresh processes, start-up query only")
    for agent in AGENTS:
        for memory, _h, task, state, waiting in q(g, Q.STARTUP, me=agent):
            say("  " + startup_line(agent, memory, task, state, waiting))

    tick, changes, killed = 41, [], False
    while True:
        say(f"--- round {len(changes) + 1} ---")
        n = q(g, Q.PROMOTE_READY)[0][0]
        if n:
            say(f"  harness: promoted {n} task(s) to ready")
        for fid, value, support in q(g, Q.HEAL_FACTS, session="s2", tick=tick):
            say(f"  research: healed {fid.removesuffix('_v2')} -> {fid} = {value} (support {support} clean)")
            n += 1
        tick += 1
        for agent in AGENTS:
            for memory, _h, task, state, waiting in q(g, Q.STARTUP, me=agent):
                say("  " + startup_line(agent, memory, task, state, waiting))
                if state != "ready":
                    continue
                session = "s2"
                if args.kill_planner and agent == "planner" and not killed:
                    killed, session = True, "s2b"
                    tick = kill_planner(g, task, tick)
                else:
                    must(q(g, Q.CLAIM, task=task, me=agent, now=tick, lease=LEASE, session="s2"),
                         f"{agent} could not claim {task}")
                    say(f"  {agent}: claimed {task}")
                spec = fx["rework"].get(memory)
                if spec is None:
                    sys.exit(f"error: no scripted rework for {memory} (the demo scripts only {ids(fx['rework'])}; flag {fx['flag']['doc']})")
                new_id = rework(g, memory, agent, spec["text"], spec["reads"], tick, session)
                q(g, Q.COMPLETE, task=task, me=agent, tick=tick, now=tick, session=session)
                say(f"  {agent}: wrote {new_id} reads {ids(spec['reads'])}; COMPLETE {task}")
                tick += 1
                n += 1
        changes.append(n)
        say(f"round {len(changes)} changes = {n}")
        if n == 0:
            break
    say(f"fixpoint: rounds {changes}, {q(g, Q.COUNT_MEMORIES)[0][0]} memories")


# ---------------------------------------------------------------- argparse
def main(argv: list[str] | None = None) -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--graph", default="quarantine", help="FalkorDB graph name (default: quarantine)")

    ap = argparse.ArgumentParser(prog="quarantine", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("session1", parents=[common], help="reload the graph from fixture.yaml")
    p.add_argument("--slow", type=float, default=0, metavar="SECONDS", help="sleep between lines")
    p.set_defaults(run=session1)

    p = sub.add_parser("flag", parents=[common], help="flag a doc and quarantine its closure")
    p.add_argument("doc")
    p.add_argument("--reason", help="advisory text (default: the fixture's)")
    p.set_defaults(run=flag)

    p = sub.add_parser("session2", parents=[common], help="heal and rework to a fixpoint")
    p.add_argument("--kill-planner", action="store_true", help="kill the planner mid-rework; show lease takeover")
    p.set_defaults(run=session2)

    args = ap.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
