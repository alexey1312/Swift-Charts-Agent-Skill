---
name: swift-charts-hexagonal-heatmap
description: >-
  Use this skill when a Swift Charts chart should group many points into
  hexagonal cells and color each cell by a count or a metric: a hexbin
  heatmap, earthquakes or check-ins over a map, the density of a scatter plot
  too crowded to read. Also use it for the parts that chart is built from —
  axial q/r coordinates and cube rounding, a custom ChartSymbolShape hexagon
  and its perceptualUnitRect, PointPlot or PointMark symbol sizes that make
  hexagons tile, explicit chartXScale/chartYScale domains and the plot's
  aspect ratio, chartForegroundStyleScale with a Gradient and .symmetricLog,
  an outline drawn with LinePlot — and for the bugs they cause: gaps or
  overlaps between hexagons, squashed hexagons, a map squeezed into a corner,
  cells drawn over the axes, points in the wrong cell, low counts that all get
  one color. iOS 16 to the current SDK. Not for rectangular heatmaps of
  categories, MapKit overlays, Chart3D, or selection highlights.
---

# Swift Charts hexagonal heatmap

Count the observations into hexagonal cells once,
plot one hexagon symbol at each occupied cell's center,
size every hexagon from the plot's own scales,
and let a color scale show the counts.
Swift Charts draws the cells as symbols,
so the hexagons tile only when their size in points matches the grid's spacing
on both axes.

Matthaus Woolard's article *Visualising data with a hexagonal heatmap in Swift Charts*
builds this chart for New Zealand's earthquakes (`references/sources.md`).
This skill keeps its technique, corrects the parts the repository's probe found
drawing wrong, and grounds every rule in Apple's sessions, the documentation,
the SDK, or that measurement.

- Code that compiles: `references/heatmap-code.md`
- What was measured, and how: `references/measured-behavior.md`
- Which API needs which iOS: `references/api-availability.md`
- States to verify: `references/verification-matrix.md`
- Plan format: `references/recommendation-format.md`
- Citations: `references/sources.md`

## Contract

- **Phase 1 is read-only.**
  Scanning, checking the SDK, reading code and writing the plan change nothing.
- **No edits without approval of item IDs** (`references/recommendation-format.md`).
  "Make it a hexbin map" before a plan exists is a request for the plan.
- **The SDK and the deployment target decide what can be written.**
  `PointPlot` needs iOS 18 and `.symmetricLog` iOS 16.4;
  below that there is a marks version, not a guess.
- **Cite a source for every item:** a session and timestamp, a documentation page,
  or a section of `measured-behavior.md`.
  Anything else is labelled *inference*.
- **Report verification honestly.**
  A green build proves it compiles.
  Only a rendered state — a preview, a snapshot, a run — proves how it looks,
  and only for the states actually rendered.

## 1. The grid

- **Axial coordinates:** `q` counts cells along a row,
  `r` counts rows, each shifted half a cell.
  A cell of radius *R* is √3 *R* wide and 2 *R* tall;
  centers are √3 *R* apart in a row and 1.5 *R* apart between rows.
- **Round all three cube coordinates.**
  Converting a point gives fractional q and r;
  round q, r and s = −q − r, then rebuild the one that moved most.
  Rounding q and r on their own put 16.8 % of a million points in a neighboring cell
  (*Measured* §6; scanner `HEX005`).
- **Bin once, outside `body`.**
  Count per cell when the data changes and store the result:
  avoid computations during rendering and prefer stored properties
  (WWDC24 10155, 9:14 and 12:02–12:19; `HEX004`).
  Keep only occupied cells; empty areas need no marks.
- **Project before you bin, when area matters.**
  Cells in degrees are not equal on the ground:
  across New Zealand a cell at 34° S covered 24 % more ground than one at 48° S,
  and every cell was squashed east–west (*Measured* §9).
  A cylindrical equal-area projection with a standard parallel through the region
  gave every cell the same area (*Measured* §9);
  the WWDC24 sample projects coordinates before plotting too (10155, 9:02).
  Project the outline the same way.

## 2. The hexagon symbol

- **`ChartSymbolShape` requires `perceptualUnitRect`.**
  There is no default, so a hexagon with only `path(in:)` does not compile (SDK).
  The path spreads six corners over the rectangle it gets:
  top and bottom at the middle, the others a quarter of the height in.
- **Size it with `symbolSize(CGSize)`.**
  A `CGSize` draws the path in exactly that width and height,
  whatever `perceptualUnitRect` says (*Measured* §1).
  Make the width √3 *R* times the x scale and the height 2 *R* times the y scale:
  the cells tile with no gap and no overlap,
  even when the plot's ratio is off (*Measured* §2–3).
  For a gap, scale both by the same factor: 0.96 left 5.8 % of the plot empty (§2).
- **An area sets the height, not the width.**
  With the narrow perceptual rectangle (0.067, 0, 0.866, 1),
  `symbolSize(area)` draws a hexagon √area tall and 0.866 √area wide (*Measured* §1).
  The exact area is (cell height)².
  The article's (cell width)² × 0.92 makes every cell 83 % of its slot
  and leaves 29 % of the plot as gap (*Measured* §2; `HEX001`).
  An area is one number, so it fits one axis:
  on a plot whose ratio was off, 20 % of the plot was covered twice (*Measured* §3).
- **Follow the plot's size.**
  Read it with `onGeometryChange(for:of:action:)` (iOS 16) inside `chartPlotStyle`
  into `@State`, and compute the `CGSize` from it.
  The state followed a resize,
  and `ImageRenderer` drew the settled size on its first pass (*Measured* §11).
- **Key-path modifiers before `symbol` and a constant `symbolSize`.**
  Those two return plain chart content, which has no key-path modifiers;
  in the other order `swiftc` only says the expression is too complex
  (checked with `swiftc -typecheck`; `api-availability.md`).

## 3. Scales and the plot

- **Give both axes an explicit domain** (`HEX002`).
  The automatic numeric domain includes zero:
  points at longitude 166–179 and latitude −47 to −34 got x 0…200 and y −60…0,
  and the map took 6 % of the plot's width (*Measured* §4).
  Swift Charts infers scales from the data;
  `chartXScale(domain:)` and `chartYScale(domain:)` fix them
  (WWDC22 10137, 13:41–14:13), and known bounds render more efficiently
  (WWDC24 10155, 12:26).
- **Put the ratio on the plot, not on the chart.**
  `chartPlotStyle` configures the plot area's size or aspect ratio
  (WWDC22 10137, 18:27; *chartPlotStyle(content:)* documentation).
  With axes shown, `.aspectRatio` on the whole chart left the plot 1.5 % off;
  inside `chartPlotStyle` it held (*Measured* §3; `HEX009`).
  The ratio is the x domain's width over the y domain's height.
- **Clip the plot** (`HEX003`).
  An explicit domain does not clip marks:
  cells past it, and the outer half of edge cells, drew over the axis labels.
  `.chartPlotStyle { $0.clipped() }` removed them and changed nothing inside
  (*Measured* §5).
- `range: .plotDimension(padding: 0)` states the intent;
  for point symbols the default range added no padding either (*Measured* §3).

## 4. Color

- **`foregroundStyle(by:)` with the count, and a `Gradient` range**
  in `chartForegroundStyleScale(domain:range:type:)`.
  Color communicates intensity, as heat does in a forecast (WWDC22 110340, 19:52).
- **Use `.symmetricLog` for skewed counts** (`HEX006`).
  On a linear scale from 0 to 10,000, every count up to 100 got the first color.
  `.symmetricLog(slopeAtZero: s)` put a count at
  log(1 + count × s) / log(1 + maximum × s) along the ramp:
  on a domain of 0…10,000 with *s* = 1,
  counts 1, 10 and 100 landed at 0.07, 0.26 and 0.50 (*Measured* §7).
  A larger *s* gives low counts more of the ramp.
  Equal steps of color are then not equal steps of count — say so in the legend's title.
- **`.symmetricLog` is iOS 16.4** (SDK).
  Below it, a linear scale over log(1 + count) put every count at the same place;
  only the legend's labels change (*Measured* §7).
- **Keep the legend** (`HEX007`).
  For a continuous scale it is the color bar with its values (*Measured* §8),
  and color must not be the only way a chart conveys critical information
  (WWDC22 110340, 20:08).
  Hide it only when something else says what the colors mean
  (WWDC22 10137, 17:51).
- **A faint, transparent low end** lets dense cells stand out;
  check it in Dark Mode and with Increase Contrast (WWDC22 110340, 21:35).

## 5. Plots or marks

- **iOS 18 and later:** `PointPlot` takes the whole collection and key paths
  (WWDC24 10155, 9:43 and 10:21) and suits uniformly styled cells (11:34).
- **iOS 16 and 17:** `ForEach` with `PointMark`.
  It drew the same pixels as `PointPlot` (*Measured* §2).
- **Hexagons in data space** are the option with no geometry reading:
  three `AreaMark(x:yStart:yEnd:series:)` points per cell tile at any plot size
  and ratio (*Measured* §10).
  Every cell needs its own `series:` —
  without it, cells with the same count joined into one area
  (*Measured* §10; `HEX008`).
  It costs three marks per cell, and what VoiceOver reads for them was not measured.

## 6. Outline and accessibility

- **An outline is a `LinePlot` with one `series:` per segment.**
  Marks with the same series, or with none, are drawn as one line
  (*LineMark* documentation).
  Hide it from VoiceOver with `.accessibilityHidden(true)`.
- **Label every cell.**
  Charts make elements for their data by default,
  and `accessibilityLabel` and `accessibilityValue` customize them
  (WWDC22 10137, 4:25).
  Put the place first and the count in the value, spelled out
  (WWDC22 110340, 17:18).
  With thousands of cells, consider labels for regions instead (18:38; *inference*).

## Workflow

### Phase 1 — Recommend

1. **Preflight.**
   `xcodebuild -version`; the app's deployment target
   (the scan reports `ios_deployment_targets`); the project's own agent
   instructions (`AGENTS.md`, `CLAUDE.md`).
   Report the toolchain in the plan.
   Where `xcodebuild` cannot run, report
   `xcrun --sdk iphoneos --show-sdk-version` and the SDK check's header instead,
   and say `xcodebuild` was unavailable.
2. **Scan and check:**

   ```bash
   python3 scripts/heatmap_scan.py <project-root> --format json > "$TMPDIR/heatmap-scan.json"
   python3 scripts/heatmap_scan.py <project-root> --format markdown
   python3 scripts/heatmap_sdk_check.py      # iOS floor of every API above
   ```

   The scan skips dependencies and hidden directories.
   Its matches are heuristics: read the chart before a finding becomes an item.
3. **Plan** with `references/recommendation-format.md`:
   correctness first (`HEX005`, `HEX002`, `HEX001`, `HEX003`, `HEX008`),
   then the technique (`HEX004`, the plot's ratio, a size that follows the plot),
   then polish (`HEX006`, `HEX007`, labels, projection, outline).
   Mark anything above the deployment target with the gate it needs,
   or plan the marks version.
4. **Ask** which item IDs to apply.

### Phase 2 — Apply and verify

1. Apply approved items only, one group at a time; change only the lines they name.
2. Build with the project's own command after each group.
3. Re-run `heatmap_scan.py`; the resolved findings should be gone.
4. Verify the states in `references/verification-matrix.md` that the change touches,
   from fixed bins in a preview or a snapshot test.
   States not rendered are reported as *not verified*.
5. Update each item's status and hand back the report.

## Guardrails

- Do not bin in `body` or in a computed property a view reads.
- Do not round q and r on their own.
- Do not size hexagons from one axis's scale, or by an area from the cell's width.
- Do not leave the x or y domain automatic, or lock the ratio of the whole chart
  while its axes take space from the plot.
- Do not write `PointPlot` or key-path modifiers below iOS 18,
  or `.symmetricLog` below iOS 16.4, without an `if #available` gate.
- Do not hide the color legend unless something else explains the colors.
- Snapshot references move when the cell size, the domain or the ramp changes;
  say which ones and why rather than re-recording blind.
