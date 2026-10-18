# Roast Room review of Quarantine

This review ran on 2026-10-15. It records a planning decision made then, not the current state of the build.

## Installation and provenance

An earlier note said `/roast-room` was installed. That was wrong at the time: invoking it returned `Unknown skill: roast-room`, and global installation had been denied. So this review followed the downloaded **written protocol without installing it**. It did not copy global configuration or run the protocol's scripts or app. The skill was installed later; this review did not use that installed copy.

Reviewed source: [proxient/learn-roast-room](https://github.com/proxient/learn-roast-room), commit `f5e7b631a172ecc8ef5488760654ad37f24204b0`. This is the fork we inspected. We did not verify its provenance against the original creator. SkillSpector rated it risk 19/100, LOW, with MEDIUM findings and only partial reference and semantic coverage. Its note about missing tool scope was a fair caution. Its matches on the essay title "Fierce Nerds" and the prose "walk home" were false positives once we read the source. The optional paid API runner was not started.

## Method

Quick mode: four independent openings. The opening round all preferred the same option, so a real debate followed, and the smaller alternative was argued for explicitly in the second round. The protocol's scoring rules allow skipping ratification when the final spread is at most three and no seat reports a likely ruin risk. Both conditions held.

Every advisor lens was an **AI simulation based on the downloaded reference material**. They are not the real people, not endorsements, and not market validation. No historical quotations were used. An earlier, flattering council summary was not used as evidence.

| Simulated lens | Weight | A: narrow local prototype | B: repair the integrated build | C: new autonomous product |
|---|---:|---:|---:|---:|
| Product, Graham lens | 3 | 4 | 8 | 1 |
| Operations, Wickman lens | 3 | 7 | 8 | 1 |
| Strategy, Bezos lens | 2 | 4 | 8 | 1 |
| Downside, Buffett lens | 1 | 7 | 8 | 0 |

Weighted option scores: **A 5.3, B 8.0, C 0.9**. Council confidence: 8/10. Spread on B: zero. These numbers rank the work plans against each other. They say nothing about project quality or the chance of winning.

Math: A = (3×4 + 3×7 + 2×4 + 1×7) / 9; B = (3×8 + 3×8 + 2×8 + 1×8) / 9; C = (3×1 + 3×1 + 2×1 + 1×0) / 9.

## Recommendation and the real disagreement

**Choose B, and hold the release until its verification gates pass.** Before the repairs, the right call was WAIT: the fixture tests were green, but the MCP dependency was missing, the Compose path was broken, and recovery failure modes were untested. For the engineering results that followed, see [VALIDATION.md](VALIDATION.md). This council is not proof that the fixes work.

The product and strategy lenses wanted one bounded session with a real AI host over MCP before we claimed agent integration. The operations and downside lenses saw that as optional, and would cut it rather than ship unsafe core state. The decision: internal safety first, then the smallest read-only host demonstration. No new autonomous-agent framework or paid inference service is needed.

## Improvements that earned priority

1. Make complete provenance and valid claim ownership preconditions of a repair write. Test zombie writers and failures between state transitions.
2. Recover unfinished claims and unfinished completions on restart. Do not print success for a rejected write or completion.
3. Validate fixture references before resetting existing data. Test malformed inputs, multiple advisories, duplicate evidence, ties and invalid replacements.
4. Make every advertised entry point run: a locked MCP dependency, real read-only protocol calls, correct Compose paths, bind address and Host handling, packaging and persistence checks.
5. Replace disconnected decision helpers with explanations of the actual graph state. Separate the scripted worker roles clearly from external AI-host reasoning.
6. Fix the README's reversed schema arrows and its example healing query, and remove the unsupported Graphiti, performance and autonomy claims. Give teammates exact commands and what to expect.

## Graph Hacks judgment

The concept **fits** persistent agent memory and handoffs well. What the demo usefully shows is selective invalidation, explainable provenance, and recovery while unrelated work survives. Fit alone does not establish novelty, production safety or a chance of winning.

The main submission risks at the time were: no recorded final demo, reproducibility on a fresh machine, explaining the scripted roles truthfully, and any verification gate still open in the validation report. Avoid adding features just to make the project sound more autonomous.

Official criteria, read from [Graph Hacks](https://www.wemakedevs.org/hackathons/falkordb) on 2026-10-15: FalkorDB must be primary and central; the main implementation must be new work done during the event; AI coding tools are allowed; a live deployment is preferred, and a complete local setup plus a working video is accepted when deployment is not available.

The raw cards, computed scores, scan output and audit notes from this session are kept locally in `/tmp/quarantine-audit-20261015/` on the machine that ran the review. That folder is not public and not a durable link. This document records the decision. It is not an advisor endorsement.
