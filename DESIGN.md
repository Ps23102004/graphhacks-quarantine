# DESIGN.md — the Quarantine ledger (light editorial build, recorded 2026-10-17)

## World

- **Form:** a left-to-right provenance ledger. Five columns in write order: Sources, Episodes, Facts, Plan steps, Files. Each memory is a labelled chip; a ribbon joins what was read to the memory written after reading it. A healed replacement slots into the column directly under its original. The layout is deterministic: the same graph always draws the same picture.
- **Ground:** warm newsprint `#f4efe5`, ink `#17140f`. Light only: it reads in a bright room and in a screen recording. No glow, no neon, no glass.
- **Type:** serif (`ui-serif`, New York on Apple) for the title and every big numeral; system sans for UI; system mono for ids. Column headers are small caps with tracking.
- **Material:** printed paper. Contamination is ink that bleeds (a multiply-blended red stain under red chips), the receipt is a yellow highlighter pen over a dotted ink line.

## Colour roles (meaning, never decoration)

| role | value | used for |
|---|---|---|
| quarantined | `#d02818` vermilion | red chips, hot ribbons, the precise counter, ink stain |
| healed replacement | `#16804a` | twin chip outline and tint, dashed SUPERSEDES ribbon |
| naive casualty | `#c76a04` ochre, hatched | clean chips a naive wipe would destroy (comparison views only) |
| receipt path | `#ffd23f` highlighter | the selected memory's path to the source, and the chain in the inspector |
| agent identity | teal, indigo, plum, blue, olive | a 6px stripe on the left of each chip, assigned in order of appearance |

Every state also has a non-colour marker on the chip: `!` quarantined or flagged source, `+` healed, `×` naive casualty.

## Motion

- One authored moment, the **spill**: when a source is flagged, ink creeps along its ribbons and each reached chip turns red in write order, 380 ms apart, with a stain that spreads for 900 ms. The precise counter climbs with it.
- Supporting: chips settle in on arrival, the receipt highlighter draws on, comparison bars grow with `transform: scaleX`, ink dots drift along ribbons.
- `prefers-reduced-motion`: no wave delay, no draw-on, no drifting dots; colour changes only.

## Interaction

- Click a chip (or use the hidden `#sr-cells` button list with the keyboard): the inspector shows what it says, who wrote it, and the server's answer in one of four shapes; a quarantined memory highlights its whole path and reads as a sentence. Escape clears.
- Hover or focus: the chip's neighbours stay lit, the rest recede. The receipt path always stays lit.
- The three policy cards are toggles: the precise view, and two views that hatch in ochre what each naive wipe would lose.

## Layout

Desktop: a serif headline numeral over the chart (left), 400px inspector (right: policies, receipt, quarantined list, key). Below 980px: the inspector stacks under the chart and the chart scrolls sideways inside its own frame (labels stay legible). Checked at 1920, 960 and 375 wide (`scripts/check_browser.js`).
