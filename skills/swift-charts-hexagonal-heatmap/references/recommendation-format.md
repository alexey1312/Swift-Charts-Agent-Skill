# Recommendation format

Use this shape for every recommendation,
whether it comes from the scanner or from reading code.
Each item has a stable ID the developer can approve,
and nothing changes until they do.

## Per item

```markdown
### HEX-02 · Size each hexagon from both axes' scales

- **Finding:** `HEX001:Sources/Quakes/QuakeMap.swift:41` — `.symbolSize(area)` with `area = width * width * 0.92`
- **What goes wrong:** the area sets the hexagon's height, not its width,
  so every cell is 83 % of its slot and 29 % of the map is white gap;
  on a plot whose ratio is off, rows overlap instead.
- **Source:** measured-behavior.md §1–3
- **Change:** `.symbolSize(grid.symbolSize(in: plotSize, xDomain: xDomain, yDomain: yDomain, fill: 0.96))`,
  with `plotSize` read by `onGeometryChange` inside `chartPlotStyle`.
- **SDK:** `symbolSize(_: CGSize)` and the one-value `onGeometryChange` are iOS 16;
  deployment target 17.0 — no gate needed
- **Risk:** low — no data change; snapshot references of the map move.
- **Verify:** states V1, V2 and V3 (`verification-matrix.md`).
- **Status:** proposed
```

## Rules

- **IDs are stable** across a session (`HEX-01`, `HEX-02`, …).
  A scanner finding keeps its own ID (`HEX001:path:line`) in the *Finding* line.
- **One source per item:** a session and timestamp, a documentation page,
  or a section of `measured-behavior.md`.
  If the advice is your own reasoning, label it *inference* and say what it rests on.
  The article that introduced the technique is background, not a citation —
  cite what the claim rests on.
- **Say what you did not verify.**
  "It builds" is not "it looks right".
  A state not rendered is *not verified*, with the step that would verify it.
- **Order:** correctness (points in the wrong cell, a squashed or cornered map,
  gaps and overlaps, cells over the axes, joined area cells),
  then the technique (binning once, the plot's ratio, a size that follows the plot),
  then polish (the color scale, the legend, accessibility labels, projection, outline).
- **Status values:** `proposed`, `approved`, `applied`, `verified`, `blocked`
  (with the reason), `declined`, `kept` (left as is, with the reason).
- **Batch approval is fine** when the developer names it ("apply HEX-01 to HEX-04").
  "Fix everything" before a plan exists means: produce the plan.

## Report skeleton

```markdown
# Hexagonal heatmap — <screen or chart>

Toolchain: Xcode <version> (<build>), iOS <sdk> SDK · Deployment target: iOS <n>
Scan: heatmap_scan <version>, <n> files, <n> with hexagon charts

## Summary
<What the map should show, what it shows now, what the deployment target allows.>

## Correctness
## Technique
## Polish
## Kept as is
## Not verified
```
