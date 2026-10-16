"""The demo as three commands over one FalkorDB graph.

    quarantine session1 [--slow 0.4]      load Session 1 from fixture.yaml
    quarantine flag doc_7                 advisory lands: closure, baselines, receipts
    quarantine session2 [--kill-planner]  heal + rework to a fixpoint
    quarantine status                     inspect recovery status as JSON

Everything is the same statements tests/test_quarantine.py asserts; this file only prints them.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time

from quarantine import queries as Q
from quarantine.agent_runtime import recovery_status
from quarantine.answers import sentence
from quarantine.loader import connect, derive_rework, load, q, read_fixture, rework, rq, validate_fixture

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
    if args.slow < 0 or not math.isfinite(args.slow):
        sys.exit("error: --slow must be a non-negative finite number")

    fx = read_fixture(args.fixture)
    validate_fixture(fx)

    g = connect(args.graph)
    try:
        g.delete()
    except Exception as e:
        err = str(e).lower()
        if "not exist" not in err and "empty key" not in err:
            raise
    g = connect(args.graph)
    # what each memory did, from the fixture; printed the moment the loader has written it
    did: dict[str, tuple[str, str, str, int]] = {}
    for k, e in fx["episodes"].items():
        did[k] = (e.get("agent", "research"), f"extracted {e['doc']}", e["text"], e["tick"])
    for k, f in fx["facts"].items():
        did[k] = (f.get("agent", "research"), f"consolidated {ids(s['ep'] for s in f['support'])}", f["value"], f["tick"])
    for kind, agent in (("steps", "planner"), ("artifacts", "coder")):
        for k, s_ in fx[kind].items():
            did[k] = (s_.get("agent", agent), f"read {ids(s_['reads'])}", s_["text"], s_["tick"])

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
    fx = read_fixture(args.fixture)
    g = connect(args.graph)
    f = fx.get("flag") or {"doc": args.doc, "tick": 40, "reason": ""}
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
    closure = [r[0] for r in rq(g, "MATCH (m:Memory {quarantined: true}) RETURN m.id ORDER BY m.tick")]
    say(f"closure {ids(closure)}")
    for task, waiting in blocked:
        say(f"task {task}  blocked_by {ids(waiting)}")
    for (aid,) in rq(g, "MATCH (m:Artifact {quarantined: true}) RETURN m.id ORDER BY m.tick"):
        if aid not in closure_ids:
            continue                                                    # red from an earlier advisory
        hops, length, via = q(g, Q.RECEIPT, **{"from": aid, "doc": args.doc})[0]
        chain = hops[0] + "".join(f" -{t}-> {h}" for t, h in zip(via, hops[1:]))
        say(f"receipt {aid} ({length} hops): {chain}")
        say(f"  in words: {sentence(hops, via)}")


# ---------------------------------------------------------------- session 2
def kill_planner(g, task: str, tick: int) -> int:
    """Planner process s2 claims `task` and dies. Returns the tick at which a new process (s2b) holds the lease."""
    def claim(now: int, session: str):
        return q(g, Q.CLAIM, task=task, me="planner", now=now, lease=LEASE, session=session)

    # A real separate process claims the task and hangs; we SIGKILL it. Nothing of it survives except the graph.
    child = subprocess.Popen([sys.executable, "-m", "quarantine.cli", "hold", "--graph", g.name,
                              "--task", task, "--tick", str(tick)], stdout=subprocess.PIPE, text=True)
    first = child.stdout.readline().strip()
    must(first == "held", f"planner process could not claim {task}: {first!r}")
    child.kill()
    child.wait()
    say(f"  planner (process {child.pid}, session s2) claimed {task}, lease until tick {tick + LEASE} ... kill -9, exit {child.returncode}")
    for memory, _h, t, state, waiting in rq(g, Q.STARTUP, me="coder"):
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
    fx = read_fixture(args.fixture)
    g = connect(args.graph)
    must(rq(g, "MATCH (t:Task) RETURN t.id LIMIT 1"), "no rework tasks yet (run `quarantine flag DOC` first)")

    # whoever authored something with a rework task, in the order their quarantined work was written
    agents = [r[0] for r in rq(g, "MATCH (a:Agent)-[:AUTHORED]->(m:Memory)<-[:REWORKS]-(:Task) "
                                 "RETURN a.name, min(m.tick) AS t ORDER BY t")] or list(AGENTS)
    say("session 2: fresh processes, start-up query only")
    for agent in agents:
        for memory, _h, task, state, waiting in rq(g, Q.STARTUP, me=agent):
            say("  " + startup_line(agent, memory, task, state, waiting))

    max_tick_rows = rq(g, "MATCH (m:Memory) RETURN max(m.tick)")
    base_tick = max_tick_rows[0][0] if max_tick_rows and max_tick_rows[0][0] else 40
    tick, changes, killed = max(41, base_tick + 1), [], False

    while True:
        say(f"--- round {len(changes) + 1} ---")
        n = q(g, Q.PROMOTE_READY)[0][0]
        if n:
            say(f"  harness: promoted {n} task(s) to ready")
        for fid, value, support in q(g, Q.HEAL_FACTS, session="s2", tick=tick):
            say(f"  research: healed {fid.removesuffix('_v2')} -> {fid} = {value} (support {support} clean)")
            n += 1
        tick += 1
        for agent in agents:
            for memory, _h, task, state, waiting in rq(g, Q.STARTUP, me=agent):
                say("  " + startup_line(agent, memory, task, state, waiting))
                if state not in ("ready", "claimed"):
                    continue

                # scripted rework for the demo's memories, graph-derived for any other flagged doc
                spec = fx.get("rework", {}).get(memory) or derive_rework(g, memory)

                # Check if clean replacement already exists (restart / recovery case)
                rep_rows = rq(g, "MATCH (m:Memory {id: $mid})<-[:SUPERSEDES]-(r:Memory {quarantined: false}) RETURN r.id", mid=memory)
                has_clean_rep = bool(rep_rows and rep_rows[0])

                session = "s2"
                if not has_clean_rep:
                    if args.kill_planner and agent == "planner" and not killed:
                        killed, session = True, "s2b"
                        tick = kill_planner(g, task, tick)
                    else:
                        must(q(g, Q.CLAIM, task=task, me=agent, now=tick, lease=LEASE, session="s2"),
                             f"{agent} could not claim {task}")
                        say(f"  {agent}: claimed {task}")
                    new_id = rework(g, memory, agent, spec["text"], spec["reads"], tick, session, task=task,
                                    needs_regeneration=spec.get("needs_regeneration", False))
                else:
                    new_id = rep_rows[0][0]
                    # Ensure current worker has claim to complete it
                    q(g, Q.CLAIM, task=task, me=agent, now=tick, lease=LEASE, session=session)

                completed = q(g, Q.COMPLETE, task=task, me=agent, tick=tick, now=tick, session=session)
                if not completed:
                    sys.exit(f"error: {agent} could not complete {task}")

                say(f"  {agent}: wrote {new_id} reads {ids(spec['reads'])}; COMPLETE {task}")
                tick += 1
                n += 1
        changes.append(n)
        say(f"round {len(changes)} changes = {n}")
        if n == 0:
            break
    say(f"fixpoint: rounds {changes}, {rq(g, Q.COUNT_MEMORIES)[0][0]} memories")


def hold(args) -> None:
    """Claim a rework task as the Planner (session s2), then sleep until killed."""
    g = connect(args.graph)
    if not q(g, Q.CLAIM, task=args.task, me="planner", now=args.tick, lease=LEASE, session="s2"):
        print("refused", flush=True)
        sys.exit(1)
    print("held", flush=True)
    time.sleep(300)


def status_cmd(args) -> None:
    """Print graph recovery status as JSON."""
    g = connect(args.graph)
    say(json.dumps(recovery_status(g), indent=2))


# ---------------------------------------------------------------- argparse
def main(argv: list[str] | None = None) -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--graph", default="quarantine", help="FalkorDB graph name (default: quarantine)")
    common.add_argument("--fixture", default=None, help="world to load (default: fixture.yaml); e.g. fixtures/support-crew.yaml")

    ap = argparse.ArgumentParser(prog="quarantine", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("session1", parents=[common], help="reload the graph from fixture.yaml")
    p.add_argument("--slow", type=float, default=0, metavar="SECONDS", help="sleep between lines")
    p.set_defaults(run=session1)

    p = sub.add_parser("flag", parents=[common], help="flag a doc and quarantine its closure")
    p.add_argument("doc")
    p.add_argument("--reason", help="advisory text (default: the fixture's)")
    p.set_defaults(run=flag)

    p = sub.add_parser("hold", parents=[common])        # internal: the process --kill-planner kills
    p.add_argument("--task", required=True)
    p.add_argument("--tick", type=int, required=True)
    p.set_defaults(run=hold)

    p = sub.add_parser("session2", parents=[common], help="heal and rework to a fixpoint")
    p.add_argument("--kill-planner", action="store_true", help="kill the planner mid-rework; show lease takeover")
    p.set_defaults(run=session2)

    p = sub.add_parser("status", parents=[common], help="print graph recovery status as JSON")
    p.set_defaults(run=status_cmd)

    args = ap.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
