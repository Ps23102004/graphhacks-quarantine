# Aman: README, blog and submission checklist (Sat evening to Sun 11:30 EDT)

You own every word a judge reads and the submission itself. Rule for every sentence: **if you cannot point to a command or a file that proves it, cut it.** "Precise" is never used alone; say "sound, never misses a memory the poison reached through a recorded read, and much narrower than a rollback" (see `docs/COUNTERFACTUAL.md`).

## Tonight (Sat)
- [ ] Get access: accept the GitHub collaborator invite; `git clone https://github.com/Ps23102004/graphhacks-quarantine.git && cd graphhacks-quarantine && git checkout freeze-sat`.
- [ ] Fresh-clone run on YOUR laptop, README Quickstart only, word for word (Docker, `uv sync --all-extras`, `uv run pytest -q`, the three demo commands). Note every step that needed a change.
- [ ] README final pass (Claude already wrote sections 1 to 8 and "What quarantined means"; Parth reviewed). Check, line by line:
  - [ ] Every number (6 / 25 / 19, 4-hop receipt, rounds [1, 2, 2, 0], counterfactual table) matches what you saw or `docs/COUNTERFACTUAL.md`.
  - [ ] "FalkorDB is source-available (SSPL)". Never "open source" for FalkorDB.
  - [ ] Honest limits section stays: scripted agents, declared read sets, healing counts episodes not documents, no live deployment, 25 nodes.
  - [ ] AI-use disclosure is accurate (Claude and OpenAI models helped; the team ran and validated everything).
  - [ ] Team names and roles correct; license MIT for our code.
- [ ] Rules compliance check against the Graph Hacks rules page: Track 02 fit, new work inside the hackathon window, repo visibility at submit time (public or judges' access), team locked at submit, video length limit, required links.

## Blog (Sat night)
- [ ] 600 to 900 words, one image (`docs/media/hive-receipt.png` shows the receipt path; re-captured from the current page on 2026-10-17; never use an image that says "precise"). Structure: the problem (one poisoned source contaminates shared agent memory); naive fixes and their cost (25 and 19 of 25); what the graph does (6, with a path as the receipt); how we tested it (unseen random crews, counterfactual replay, ten attackers, what they found and what we fixed); honest limits; what's next.
- [ ] Every claim in the blog appears in the README or a doc. No new numbers.

## Sunday
- [ ] 09:00 to 10:00: Parth sends the video link; check it is 3:00 or less, unlisted, plays logged out.
- [ ] 10:00 to 11:30: submission form: repo link, video link, blog link, track 02, team members, short description (use the README's first paragraph), AI-use disclosure.
- [ ] Before pressing submit: repo visibility correct for judges; README renders on GitHub; the tag or commit you submit is the one Aashna validated.
- [ ] Screenshot the confirmation page and send it to the team.
