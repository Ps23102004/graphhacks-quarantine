"""Held-out evaluation: random crews the demo never saw, graph vs independent oracle.

    uv run python scripts/heldout_eval.py [--worlds 300]   # prints a markdown report

Seeds start at 1000 (tests use 2000+ and 3000+; nothing here was used to tune the queries).
"""
from __future__ import annotations

import argparse

from quarantine.heldout import run, summarize

ap = argparse.ArgumentParser()
ap.add_argument("--worlds", type=int, default=300)
n = ap.parse_args().worlds

rows = []
for label, mode, deep in (("declared read sets (the demo's model)", "declared", False),
                          ("cumulative context (pessimistic)", "cumulative", False),
                          ("deep chains", "declared", True)):
    s = summarize(run(range(1000, 1000 + n), mode, deep, graph="heldout_report"))
    rows.append((label, s))

print(f"| world model | (world, flagged doc) cases | graph != oracle | precise quarantine | naive: wipe agents | naive: time-based | clean memories lost: wipe agents | clean memories lost: time-based |")
print("|---|---|---|---|---|---|---|---|")
for label, s in rows:
    print(f"| {label} | {s['cases']} | {s['mismatched']} | {s['mean_precise_frac']:.0%} | {s['mean_per_agent_frac']:.0%} | "
          f"{s['mean_time_frac']:.0%} | {s['clean_lost_per_agent']:.0%} | {s['clean_lost_time']:.0%} |")
print("\nPercentages are the mean share of all memories in a world that each policy discards, over every case where the doc taints anything.")
