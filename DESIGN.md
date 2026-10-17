# DESIGN.md — the Quarantine hive (recorded from the built page, 2026-10-17)

## World

- **Form:** a hive plot. Five radial axes around a quiet core, one per kind of memory, in provenance order: Sources (top), Episodes, Facts, Plan steps, Files (clockwise, 72° apart). Each memory is a hexagonal cell placed on its axis by write order. Provenance is a curved arc pulled toward the core; a read between two cells on the same axis bows outward. No force layout, no physics: the picture is the same every time the same graph is loaded.
- **Ground:** graphite night `#0b0d12` with one soft radial lift behind the hive. Chosen for the recording scene and dim demo rooms; there is no light theme.
- **Material:** Apple-style translucent layers: the sticky top bar and the inspector column use `backdrop-filter` blur over the ground; cards are one step lighter glass with a 1px hairline (`rgba(255,255,255,.08)`), radius 14px. `prefers-reduced-transparency` makes them solid.
- **Type:** the platform system face (SF on Apple devices) at body 15px; numbers tabular; large counters 38px weight 650 tracking -0.03em; ids in the system monospace.

## Colour roles (meaning, never decoration)

| role | value | used for |
|---|---|---|
| clean memory | `#2a3140` fill | default cell |
| quarantined | `#ff453a` (system red) | red cells, hot arcs, the precise counter |
| healed replacement | `#30d158` (system green) | twin cells beside their original, dashed SUPERSEDES arc |
| naive casualty | `#ff9f0a` (system orange) | clean cells a naive wipe would destroy (only in the two comparison views) |
| receipt path | `#ffd60a` (system yellow) | the selected memory's path to the source, and the chain in the inspector |
| agent rims | `#64d2ff`, `#7d7aff`, `#da8fff`, `#66d4cf`, `#ffb340` | each author's cells carry its rim colour, assigned in order of appearance |

Every state also has a non-colour marker inside the cell: `!` quarantined or flagged source, `+` healed, `×` naive casualty.

## Motion

- One authored moment: the **red wave**. When a source is flagged, cells turn red in the order they were written, 360 ms apart, each with a short halo burst, and the arcs into them draw on with a stroke-dash (900 ms, ease `cubic-bezier(.16,1,.3,1)`). The precise counter climbs with the wave.
- Supporting motion: new cells settle in (scale .4 to 1, 520 ms); the receipt path draws on (700 ms); comparison bars grow with `transform: scaleX`; the live dot breathes.
- `prefers-reduced-motion`: no wave delay, no draw-on, no bursts; colour changes only.

## Interaction

- Click, or focus and press Enter/Space, on any cell: the inspector shows what it says, who wrote it and when, and the server's answer in one of four shapes; for a quarantined memory the path to the source lights up and reads as a sentence. Escape clears.
- Hover or focus: the cell's neighbours stay lit, everything else recedes.
- The three policy cards are toggles: the precise view, and two views that paint in orange what each naive wipe would lose.
- Labels: sources and quarantined cells are labelled; every other label appears on hover, focus or selection. Labels run perpendicular to their axis, so neighbours never collide.

## Layout

Desktop: hive on the left, 400px inspector on the right (policies, receipt, ledger, key). Below 980px: header wraps, hive becomes a square, inspector stacks under it. Checked at 1920, 1600, 960 and 375 wide (`scripts/check_browser.js`).
