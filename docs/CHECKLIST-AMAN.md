# Aman: README, blog and submission checklist (Sat evening to Sun 11:30 EDT)

## Status Sun 2026-10-18

- README: Aman rewrote it on Oct 17 (commit 21c94f2) and edited it again that evening (591bbd2). Parth merged those edits with the current engine, numbers and limits.
- Blog draft `docs/BLOG.md` and submission text `docs/SUBMISSION.md`: drafted by Parth with Claude on Oct 18 so the work was not blocked. Aman can edit both.
- Fresh clone: Parth ran one from GitHub on macOS on Oct 18 with Claude. A clone on Aman's laptop was not run.
- Video: recorded and public, https://youtu.be/BZ3Qp1WWYB8 (2:51); the README and docs/SUBMISSION.md link it.

The plan as written on Saturday follows.

---

You own every word a judge reads, and the submission itself. Rule for every sentence: **if you cannot point to a command or a file that proves it, cut it.** Do not use "precise". Say: "marks every memory whose recorded reads lead back to the source; misses influence that was never recorded (7% in our generated crews); about 63% of what it flags would not have changed" (see `docs/COUNTERFACTUAL.md`).

## Tonight (Sat)
- [ ] Get access: accept the GitHub collaborator invite; `git clone https://github.com/Ps23102004/graphhacks-quarantine.git && cd graphhacks-quarantine && git checkout freeze-sat`.
- [ ] Fresh-clone run on YOUR laptop, README "Run it locally" steps only, word for word (Docker, `uv sync --all-extras`, `uv run pytest -q`, the three demo commands). Note every step that needed a change.
- [ ] README final pass. Check, line by line:
  - [ ] Every number (6 / 25 / 19, the 4-hop receipt, rounds [1, 2, 2, 0], the counterfactual table) matches what you saw or `docs/COUNTERFACTUAL.md`.
  - [ ] "FalkorDB is source-available (SSPL)". Never call FalkorDB "open source".
  - [ ] The limits section stays: scripted agents, declared read sets, healing counts episodes not documents, no live deployment, 25 nodes.
  - [ ] The AI-use disclosure matches what happened (Claude and OpenAI models helped; say only what the team actually ran).
  - [ ] Team names and roles are correct; the license for our code is MIT.
- [ ] Rules check against the Graph Hacks rules page: Track 02 fit, new work inside the hackathon window, repo visibility at submit time, team locked at submit, video length limit, required links.

## Blog (Sat night)
- [ ] 600 to 900 words, one image. `docs/media/hive-receipt.png` shows the receipt path; it was captured from the page on 2026-10-17. Never use an image that says "precise". Structure: the problem (one poisoned source contaminates shared agent memory); naive fixes and their cost (25 and 19 of 25); what the graph does (6, with a path as the receipt); how we tested it (unseen random crews, counterfactual replay, ten attackers, what they found and what we fixed); honest limits; what's next.
- [ ] Every claim in the blog appears in the README or a doc. No new numbers.

## Sunday
- [ ] 09:00 to 10:00: Parth sends the video link. Check it is 3:00 or less (it was published public, 2:51), and plays logged out.
- [ ] 10:00 to 11:30: submission form: repo link, video link, blog link, Track 02, team members, short description (from `docs/SUBMISSION.md`), AI-use disclosure.
- [ ] Before pressing submit: the repo is public; the README renders on GitHub; the submitted commit is the one that passed the checks.
- [ ] Screenshot the confirmation page and send it to the team.
