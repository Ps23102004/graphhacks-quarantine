# Roast Room review of Quarantine

## Installation and provenance

The earlier claim that `/roast-room` was installed was incorrect. Native invocation returned `Unknown skill: roast-room`; global installation had been denied. This review used the downloaded **written protocol without installing it**, copying global configuration or executing its scripts/app.

Reviewed source: [proxient/learn-roast-room](https://github.com/proxient/learn-roast-room), commit `f5e7b631a172ecc8ef5488760654ad37f24204b0`. This is the inspected fork, not a claim that its provenance was verified against the video's creator. SkillSpector reported risk 19/100, LOW, with MEDIUM findings and partial reference/semantic coverage. Missing tool scope was a valid caution; matches on the essay title “Fierce Nerds” and prose “walk home” were false positives after inspecting source. The optional paid API runner was not started.

## Method

Quick mode: four independent openings, then a genuine debate after the opening round unanimously preferred the same option. The smaller alternative was explicitly defended in the second round. The reviewed scoring rules allow skipping ratification when final spread is at most three and no seat reports likely ruin risk; both conditions held.

All advisor lenses were **AI simulations based on the downloaded reference material**. They were not the real people, endorsements or independent market validation. No historical quotations were needed. The former flattering council summary was not used as evidence.

| Simulated lens | Weight | A: narrow local prototype | B: repair integrated build | C: new autonomous product |
|---|---:|---:|---:|---:|
| Product, Graham lens | 3 | 4 | 8 | 1 |
| Operations, Wickman lens | 3 | 7 | 8 | 1 |
| Strategy, Bezos lens | 2 | 4 | 8 | 1 |
| Downside, Buffett lens | 1 | 7 | 8 | 0 |

Weighted option preferences: **A 5.3, B 8.0, C 0.9**. Council confidence: 8/10. Spread on B: zero. These numbers express preferences among the work plans, **not project quality or probability of winning**.

Math: A = (3×4 + 3×7 + 2×4 + 1×7) / 9; B = (3×8 + 3×8 + 2×8 + 1×8) / 9; C = (3×1 + 3×1 + 2×1 + 1×0) / 9.

## Recommendation and actual disagreement

**Choose B, with release held until its verification gates pass.** The pre-repair state warranted WAIT: green fixture tests coexisted with a missing MCP dependency, a broken Compose path and untested recovery failure modes. See [VALIDATION.md](VALIDATION.md) for the subsequent engineering results rather than interpreting this council as proof that fixes work.

The product and strategy lenses wanted one bounded real AI-host MCP session before claiming agent integration. Operations and downside lenses considered it optional proof and would cut it rather than ship unsafe core state. The implementation decision is internal safety first, then the smallest read-only host demonstration. No new autonomous-agent framework or paid inference service is required.

## Improvements that earned priority

1. Make complete provenance and valid claim ownership prerequisites of a repair write. Test zombie writers and failures between state transitions.
2. Recover unfinished claims and unfinished completions on restart. Do not print success for rejected writes or completion.
3. Validate fixture references before resetting existing data. Test malformed inputs, multiple advisories, duplicate evidence, ties and invalid replacements.
4. Make advertised entrypoints run: locked MCP dependency, real read-only protocol calls, correct Compose paths/bind/Host handling, packaging and persistence checks.
5. Replace disconnected decision helpers with explanations of actual graph state. Clearly separate scripted worker roles from external AI-host reasoning.
6. Correct the README's reversed schema arrows, example healing query and unsupported Graphiti/performance/autonomy claims. Give teammates exact commands and acceptance evidence.

## Graph Hacks judgment

The concept is a strong **fit** for persistent agent memory and handoffs. Its useful demonstration is selective invalidation, explainable provenance and recovery while unrelated work survives. That fit does not establish novelty, production safety or winning chances.

Main remaining submission risks are an unrecorded final demo, fresh-machine reproducibility, truthful explanation of the scripted roles, and any verification gate still open in the current validation report. Avoid adding features solely to make the project sound more autonomous.

Official criteria checked against [Graph Hacks](https://www.wemakedevs.org/hackathons/falkordb): FalkorDB must be primary and central; main implementation must be new event work; AI coding tools are allowed; a live deployment is preferred, with complete local setup and a working video accepted when deployment is unavailable.

Raw cards, computed scores, scan output and audit evidence from this session are retained locally under `/tmp/quarantine-audit-20261015/`; that temporary directory is not a public or durable report URL. This document records the decision, not a fabricated advisor endorsement.
