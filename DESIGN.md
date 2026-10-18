# DESIGN.md: the Quarantine ledger (light build, 2026-10-17)

## World

- **Form:** a provenance ledger read left to right. Five columns in write order: Sources, Episodes, Facts, Plan steps, Files. Each memory is a labelled chip. A ribbon joins what was read to the memory written after reading it. A healed replacement sits in the same column, right under its original. Chip positions are computed from the graph alone, so the same graph always gets the same layout.
- **Background:** warm newsprint `#f4efe5`, ink `#17140f`. Light only, so it reads in a bright room and in a screen recording. No glow, no neon, no glass.
- **Type:** serif (`ui-serif`, New York on Apple) for the title and the big numerals. System sans for the interface, system mono for ids. Column headers are uppercase with letter spacing.
- **Material:** printed paper. Contamination is ink that bleeds: a red stain, blended with multiply, under each red chip. The receipt is a yellow highlighter over a dotted ink line.

## Colour roles (each colour means one thing)

| role | value | used for |
|---|---|---|
| quarantined | `#d02818` vermilion | red chips, hot ribbons, the quarantine counter, ink stain |
| healed replacement | `#16804a` green | twin chip outline and tint, dashed SUPERSEDES ribbon |
| naive casualty | `#c76a04` ochre, hatched | clean chips a naive wipe would destroy (comparison views only) |
| receipt path | `#ffd23f` highlighter | the selected memory's path to the source, and the chain in the inspector |
| agent identity | teal, indigo, plum, blue, olive | a 6px stripe on the left of each chip, assigned in order of appearance |

Every state also has a marker that is not a colour: `!` quarantined or flagged source, `+` healed, `?` placeholder waiting for regeneration, `×` naive casualty.

## Motion

- One staged moment, the **spill**. When a source is flagged, ink runs along its ribbons and each reached chip turns red in write order, 380 ms apart. Under each one a stain spreads for 900 ms. The quarantine counter climbs as the chips turn.
- Smaller motion: chips settle in when they arrive, the receipt highlighter draws on, comparison bars grow with `transform: scaleX`, and ink dots drift along the ribbons.
- With `prefers-reduced-motion`: no wave delay, no draw-on, no drifting dots. Only the colours change.

## Interaction

- Click a chip, or use the hidden `#sr-cells` button list from the keyboard. The inspector shows what the memory says, who wrote it, and the server's answer in one of four shapes. For a quarantined memory it highlights the whole path and states it as a sentence. Escape clears.
- Hover or focus a chip: its neighbours stay lit and the rest fade. The receipt path always stays lit.
- The three policy cards are toggles: the graph view, and two views that hatch in ochre what each naive wipe would lose.

## Layout

Desktop: a big serif numeral above the chart on the left, a 400px inspector on the right (policies, receipt, quarantined list, key). Below 980px wide, the inspector moves under the chart, and the chart scrolls sideways inside its own frame so labels stay readable. `scripts/check_browser.js` checks it at 1920, 960 and 375 wide.
