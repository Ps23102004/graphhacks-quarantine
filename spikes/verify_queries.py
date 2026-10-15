"""Run every hero query in demo order against the fixture and print raw output.
This is the evidence behind the VERIFIED marks in plans QUERIES.md.

    uv run python spikes/verify_queries.py > spikes/verify-results.txt
"""
from quarantine import queries as Q
from quarantine.loader import connect, load, q, read_fixture, rework

fx = read_fixture()
g = connect("quarantine_verify")
try:
    g.delete()
except Exception:
    pass
g = connect("quarantine_verify")
load(g, fx)
flag = fx["flag"]


def show(name, cypher, **params):
    print(f"\n=== {name}  params={params}")
    print(cypher.strip())
    rows = q(g, cypher, **params)
    print(f"--> {len(rows)} row(s)")
    for r in rows:
        print("   ", r)
    return rows


show("COUNT_MEMORIES (Session 1 loaded)", Q.COUNT_MEMORIES)
show("FLAG_DOC", Q.FLAG_DOC, doc=flag["doc"], reason=flag["reason"], tick=flag["tick"])
show("Q1 TAINT_CLOSURE", Q.TAINT_CLOSURE, doc=flag["doc"], tick=flag["tick"])
show("Q2 NAIVE_PER_AGENT", Q.NAIVE_PER_AGENT, doc=flag["doc"])
show("Q2b NAIVE_TIME_BASED", Q.NAIVE_TIME_BASED, doc=flag["doc"])
show("Q3 RECEIPT (shortestPath)", Q.RECEIPT, **{"from": "a_requirements", "doc": flag["doc"]})
show("Q3b RECEIPT_SPPATHS (algo.SPpaths)", Q.RECEIPT_SPPATHS, **{"from": "a_requirements", "doc": flag["doc"]})
show("Q3 RECEIPT for a clean artifact (null path)", Q.RECEIPT, **{"from": "a_fetch_py", "doc": flag["doc"]})
show("Q4a SUPPORT_AND_HEALABLE", Q.SUPPORT_AND_HEALABLE)
show("Q7 CREATE_REWORK_TASKS", Q.CREATE_REWORK_TASKS, tick=flag["tick"])
show("Q7 CREATE_BLOCKED_BY", Q.CREATE_BLOCKED_BY)
for a in ("research", "planner", "coder"):
    show(f"Q6 STARTUP {a} (before heal)", Q.STARTUP, me=a)
show("RED_WAVE (after closure)", Q.RED_WAVE)

print("\n##### Session 2 rounds (scheduler: promote, heal, then ready work per agent)")
tick = 41
for rnd in range(1, 6):
    print(f"\n----- round {rnd}")
    n = show("Q5 PROMOTE_READY", Q.PROMOTE_READY)[0][0]
    healed = show("Q4b HEAL_FACTS", Q.HEAL_FACTS, session="s2", tick=tick)
    tick += 1
    n += len(healed)
    for agent in ("planner", "coder"):
        for memory, _h, task, state, _w in show(f"Q6 STARTUP {agent}", Q.STARTUP, me=agent):
            if state == "ready":
                spec = fx["rework"][memory]
                show("Q8 CLAIM", Q.CLAIM, task=task, me=agent, now=tick, lease=5, session="s2")
                new = rework(g, memory, agent, spec["text"], spec["reads"], tick, "s2")
                print(f"    rework() wrote {new} reads={spec['reads']}")
                show("Q8b COMPLETE", Q.COMPLETE, task=task, me=agent, tick=tick)
                tick += 1
                n += 1
    print(f"round {rnd} changes = {n}")
    if n == 0:
        break

show("RED_WAVE (after Session 2)", Q.RED_WAVE)
show("COUNT_MEMORIES (after Session 2)", Q.COUNT_MEMORIES)
for name in ("AUDIT_NO_FORWARD_INFLUENCE", "AUDIT_CLEAN_NEVER_CITES_QUARANTINED", "AUDIT_CLOSURE_IS_CLOSED"):
    show(name, getattr(Q, name))
show("lineage kept: superseded chain", "MATCH (n:Memory)-[:SUPERSEDES]->(o:Memory) RETURN n.id, o.id, o.quarantined, n.quarantined ORDER BY n.tick")
g.delete()
