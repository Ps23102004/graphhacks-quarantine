"""Held-out evaluation: random crews the demo never saw, graph vs independent oracle.

    uv run python scripts/heldout_eval.py [--worlds 300]   # prints a markdown report

Seeds start at 1000 (tests use 2000+ and 3000+; nothing here was used to tune the queries).
"""
from __future__ import annotations

import argparse

from quarantine.heldout import run, run_pipelines, summarize

ap = argparse.ArgumentParser()
ap.add_argument("--worlds", type=int, default=300)
ap.add_argument("--pipeline-worlds", type=int, default=100, help="worlds for the whole-Session-2 runs (slower)")
args = ap.parse_args()
n = args.worlds

rows = []
for label, mode, deep in (("declared read sets (the demo's model)", "declared", False),
                          ("cumulative context (pessimistic)", "cumulative", False),
                          ("deep chains", "declared", True)):
    s = summarize(run(range(1000, 1000 + n), mode, deep, graph="heldout_report"))
    rows.append((label, s))

print(f"| world model | (world, flagged doc) cases | graph != oracle | graph quarantine | naive: wipe agents | naive: time-based | clean memories lost: wipe agents | clean memories lost: time-based |")
print("|---|---|---|---|---|---|---|---|")
for label, s in rows:
    print(f"| {label} | {s['cases']} | {s['mismatched']} | {s['mean_precise_frac']:.0%} | {s['mean_per_agent_frac']:.0%} | "
          f"{s['mean_time_frac']:.0%} | {s['clean_lost_per_agent']:.0%} | {s['clean_lost_time']:.0%} |")
print("\nPercentages are the mean share of all memories in a world that each policy discards, over every case where the doc taints anything.")

print("\n| whole Session 2 on unseen worlds (flag, heal, claim, derived rework, fixpoint) | worlds | (world, doc) runs | invariant violations |")
print("|---|---|---|---|")
for label, mode, deep in (("declared read sets", "declared", False), ("cumulative context", "cumulative", False), ("deep chains", "declared", True)):
    total, fails = run_pipelines(range(1000, 1000 + args.pipeline_worlds), mode, deep, graph="heldout_report_pipe")
    print(f"| {label} | {args.pipeline_worlds} | {total} | {len(fails)} |")
