"""Counterfactual evaluation: replay each unseen world without the poisoned document and compare with the graph.

    uv run python scripts/counterfactual_eval.py [--worlds 150]

Exit 1 if any false negative, invented receipt, wrong 'clean' answer or page mismatch is found.
Seeds 7000 and up (never used to tune a query or rule).
"""
from __future__ import annotations

import argparse
import sys

from quarantine.counterfactual import run

ap = argparse.ArgumentParser()
ap.add_argument("--worlds", type=int, default=150)
ap.add_argument("--start", type=int, default=7000)
args = ap.parse_args()

hard = 0
print("| world model | (world, doc) runs | truly affected | quarantined | false negatives | needless flags | needless facts that cannot heal | invented receipts | wrong 'clean' answers | page != graph |")
print("|---|---|---|---|---|---|---|---|---|---|")
for label, mode, deep in (("declared read sets", "declared", False), ("cumulative context", "cumulative", False), ("deep chains", "declared", True),
                          ("UNRECORDED influence (graph: declared reads; truth: whole context)", "hidden", False)):
    t = run(range(args.start, args.start + args.worlds), mode, deep)
    # hidden mode is expected to miss memories: it measures what incomplete read sets cost, it is not a pass/fail gate
    hard += (0 if mode == "hidden" else len(t.false_negatives)) + len(t.bad_receipts) + len(t.bad_clean_answers) + len(t.page_mismatch)
    missed = sum(len(x[3]) for x in t.false_negatives)
    print(f"| {label} | {t.runs} | {t.affected} | {t.flagged} | {len(t.false_negatives)} runs, {missed} memories ({missed / max(t.affected, 1):.0%} of truly affected) | {t.needless} ({t.needless / max(t.flagged, 1):.0%} of flagged) | "
          f"{t.needless_unhealable_facts} | {len(t.bad_receipts)} | {len(t.bad_clean_answers)} | {len(t.page_mismatch)} |")
    print(f"<!-- needless by kind: {dict(t.needless_by_kind)} first problems: {(t.false_negatives + t.bad_receipts + t.bad_clean_answers + t.page_mismatch)[:2]} -->")
sys.exit(1 if hard else 0)
