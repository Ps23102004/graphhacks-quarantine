# Launch assets

A 20-second clip, `docs/media/launch-20s.mp4`, made from five real screenshots of the page (no mock-ups), with captions added on top. It is a teaser, not the demo video. Every number in it comes from the bundled demo: 6 quarantined, 25 for a full agent wipe, 19 for a time rollback.

## 20-second script (matches the clip)

| time | on screen | caption |
|---|---|---|
| 0:00 to 0:03 | the ledger before any flag, 25 memories | "One poisoned page can corrupt every agent's memory." |
| 0:03 to 0:08 | the page after `flag doc_7`: red ink, "6 of 25 memories" | "Flag it: 6 of 25 memories quarantined. Wiping every agent it touched would discard 25. Rolling back by time, 19." |
| 0:08 to 0:12 | `a_requirements` selected, yellow path back to `doc_7` | "Every red memory has a receipt. The path back to the source, as a sentence. The coder never read the bad page." |
| 0:12 to 0:16 | healed state with green replacements | "One Cypher traversal. Rebuilt from unquarantined episodes. Agents in this demo are scripted." |
| 0:16 to 0:20 | end card | "Quarantine. Forget what a bad source reached. Keep the rest. github.com/Ps23102004/graphhacks-quarantine" |

## Post (X, LinkedIn)

We built QUARANTINE for Graph Hacks 2026 (Track 02, agent memory).

When a source in shared agent memory turns out to be poisoned, most fixes either wipe every agent that touched it or roll memory back by time. In our demo that discards 25 or 19 of 25 memories. QUARANTINE follows the recorded reads in a FalkorDB graph and marks 6, with a path back to the source for each one.

It is a prototype. The agents are scripted. It follows provenance, so about 63% of what it flags in our generated test crews would have kept the same content, and it misses influence nobody recorded (7% of the truly affected memories in those crews). The numbers, the method and the command to rerun them are in the repo.

github.com/Ps23102004/graphhacks-quarantine

## Banner

A wide crop of `docs/media/hive-receipt.png` (the ledger with the yellow receipt path) works as a README header. Keep the title "Quarantine" in the page's serif and no extra claims in the image.
