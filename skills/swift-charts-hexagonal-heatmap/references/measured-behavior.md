# Measured behavior

The skill's *Measured* statements come from `scripts/probes/hexagon_probe.swift`
in this repository.
Run it to re-derive every number below:

```bash
xcrun swiftc -O -suppress-warnings scripts/probes/hexagon_probe.swift -o "$TMPDIR/hexagon_probe"
"$TMPDIR/hexagon_probe" --png "$TMPDIR/hexagon-probe"   # --png also writes each render
```

**Setup.**
macOS 27.0 (26A428), Xcode 27.1 (27A9269), 2026-10-06.
Charts rendered with `ImageRenderer` at 1× (§1 at 4×) and measured pixel by pixel;
§3, §4, §5, §8 and §11 host the chart in an offscreen `NSHostingView`
to read its `ChartProxy` or its geometry.
Two runs gave identical output.

The tiling charts plot a grid of pointy-top hexagons of radius 1
on a domain 16 wide and 12 tall,
in a plot 480 × 360 pt — 30 pt per unit both ways —
with hidden axes and explicit scales.
The hexagons are black at 50 % opacity on white,
so a pixel that no hexagon covers stays white
and a pixel that two hexagons cover turns dark.
*Gap* and *overlap* are those pixels' share of an inner region
away from the grid's ragged border.

**Scope.**
Swift Charts is one framework on iOS and macOS,
and these are measurements of its layout, symbols, scales and drawing.
They were not repeated on an iOS simulator.

## §1 The symbol's drawing box

One `PointMark`, measured at 4×:

| Symbol | Size | Drawn |
| --- | --- | --- |
| Square path, `perceptualUnitRect` 0, 0, 1, 1 | `symbolSize(1600)` | 40.0 × 40.0 pt |
| `.circle` | `symbolSize(1600)` | 45.0 × 45.0 pt |
| Hexagon path, `perceptualUnitRect` 0, 0, 1, 1 | `symbolSize(1600)` | 40.0 × 40.0 pt |
| Hexagon path, `perceptualUnitRect` 0.067, 0, 0.866, 1 | `symbolSize(1600)` | 34.5 × 40.0 pt |
| The same | `symbolSize(400)` | 17.5 × 20.0 pt |
| The same | size scale 0…1 → 0…1600, value 1 | 34.5 × 40.0 pt |
| Hexagon path, `perceptualUnitRect` 0, 0, 1, 1 | `symbolSize(CGSize(34.64, 40))` | 34.5 × 40.0 pt |
| Hexagon path, `perceptualUnitRect` 0.067, 0, 0.866, 1 | `symbolSize(CGSize(34.64, 40))` | 34.5 × 40.0 pt |

- An area is the square of the side for a square symbol.
  The circle is drawn larger, so that it looks as large as the square.
- With the narrow perceptual rectangle,
  the hexagon is as **tall** as the square root of the area
  and 0.866 times as wide —
  the regular proportions, but the area does not set the width.
- `symbolSize(CGSize)` draws the path in exactly that width and height,
  whatever the perceptual rectangle says.
- A size scale whose range ends at the area draws the same box as the area itself:
  the article's gist uses this to keep the area out of the chart content.

`ChartSymbolShape` declares `perceptualUnitRect` as a requirement with no default
(SDK, and `swiftc` rejects a conformance without it).
The article's first `Hexagon`, which has only `path(in:)`, does not compile.

## §2 Tiling

| Size of every hexagon | Gap | Overlap |
| --- | ---: | ---: |
| Narrow rectangle, area = (cell width)² × 0.92 = 2,483 — the article's formula | 29.4 % | 0.0 % |
| Narrow rectangle, area = (cell height)² = 3,600 | 0.0 % | 0.0 % |
| `symbolSize(CGSize(cell width, cell height))` | 0.0 % | 0.0 % |
| The same, `ForEach` + `PointMark` instead of `PointPlot` | 0.0 % | 0.0 % |
| `CGSize` × 0.96 each way | 5.8 % | 0.0 % |

The cell is √3 × radius wide and 2 × radius tall in data units.
The article squares the cell's width and takes 92 % of it, meaning a small gap;
but the area sets the height (§1),
so its hexagons are 83 % of a cell each way
and 29 % of the plot stays empty.
The exact area is the square of the cell's **height**.

`PointPlot` and `ForEach` + `PointMark` drew identical pixels (0 px differ).

## §3 Plot proportions

The same grid, in a 480 × 480 frame:

| Layout | Plot | Ratio (4:3 = 1.333) | y scale against x |
| --- | --- | --- | --- |
| Axes hidden, `.aspectRatio(4/3)` on the chart | 480.0 × 360.0 pt | 1.333 | 0.0 % |
| Axes shown, `.aspectRatio(4/3)` on the chart | 463.0 × 342.0 pt | 1.354 | −1.5 % |
| Axes shown, `.chartPlotStyle { $0.aspectRatio(4/3) }` | 463.0 × 348.0 pt | 1.330 | 0.2 % |

The axes take space from the plot,
so a ratio on the whole chart is not the plot's ratio;
a ratio inside `chartPlotStyle` is (the 0.2 % is whole-point rounding).

An explicit domain with no `range:` put the domain's ends on the plot's edges,
the same as `.plotDimension(padding: 0)` —
for point symbols, the default added no padding.

On a plot whose ratio is wrong — 480 × 300 pt, so 30 pt per unit across and 25 down:

| Size | Gap | Overlap |
| --- | ---: | ---: |
| Area = (cell height by the x scale)² | 0.0 % | 20.0 % |
| `symbolSize(CGSize(√3 × 30, 2 × 25))` | 0.0 % | 0.0 % |

An area is one number, so it fits one axis.
A `CGSize` from each axis's own scale tiles
(the hexagons are then stretched, not regular).

## §4 Automatic domains

Three points at longitude 166.4…178.6 and latitude −47.2…−34.1,
no `chartXScale` or `chartYScale`:

| Axis | Domain the chart chose |
| --- | --- |
| x | 0 … 200 |
| y | −60 … 0 |

The automatic numeric domain includes zero.
The data took 12.2° of a 200° wide domain — 6 % of the plot's width —
in the corner nearest zero.

## §5 Cells past an explicit domain

x domain 0…10, axes shown,
one red hexagon centered at x 10.6 (outside) and one at x 9.8 (inside, near the edge):

| Plot style | Red pixels right of the plot | Inside it |
| --- | ---: | ---: |
| Default | 218 | 466 |
| `.chartPlotStyle { $0.clipped() }` | 0 | 466 |

An explicit domain does not clip marks:
a cell past the domain, and the outer half of a cell on its edge,
draw over the axis labels.
`clipped()` on the plot removes them and changes nothing inside.

## §6 Binning

1,000,000 uniformly random points (seeded) over longitude 164…180 and latitude −48.5…−33.5,
radius 0.3,
each compared with the cell whose center is nearest:

| Rounding | Points in the wrong cell |
| --- | ---: |
| q and r rounded independently | 16.77 % |
| Cube rounding: round q, r and s = −q − r, rebuild the one that moved most | 0.00 % |

## §7 Where counts land on the color ramp

Domain 0…10,000 on a black-to-white gradient;
0 is the start of the ramp and 1 the end,
read from the rendered gray and calibrated against the linear scale.

| Scale | 1 | 10 | 100 | 1,000 | 10,000 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `.linear` | 0.000 | 0.000 | 0.000 | 0.100 | 1.000 |
| `.symmetricLog` | 0.067 | 0.258 | 0.500 | 0.750 | 1.000 |
| `.symmetricLog(slopeAtZero: 1)` | 0.067 | 0.258 | 0.500 | 0.750 | 1.000 |
| `.symmetricLog(slopeAtZero: 0.1)` | 0.000 | 0.100 | 0.350 | 0.667 | 1.000 |
| `.symmetricLog(slopeAtZero: 10)` | 0.208 | 0.400 | 0.600 | 0.800 | 1.000 |
| `.linear` over log(1 + count), domain 0…log(1 + 10,000) | 0.067 | 0.258 | 0.500 | 0.750 | 1.000 |

- On a linear scale every count up to 100 got the first color of the ramp.
- `.symmetricLog` is `.symmetricLog(slopeAtZero: 1)`.
- The positions fit **t = log(1 + count × slopeAtZero) / log(1 + maximum × slopeAtZero)**
  within 0.009, 0.014 and 0.001 for slopes 1, 0.1 and 10:
  a larger `slopeAtZero` gives low counts more of the ramp.
- A linear scale over log(1 + count) put every count where `.symmetricLog` did —
  the route below iOS 16.4, where `.symmetricLog` does not exist.
  Its legend labels the log values, not the counts.

## §8 Legend of a continuous color scale

`foregroundStyle(by:)` with a numeric value and a `Gradient` range,
chart 400 × 300 pt, axes hidden:

| Legend | Plot height | Below the plot |
| --- | ---: | --- |
| Default | 260 pt | a 124 pt color bar with value labels 0, 25, 50, 75, 100 |
| `.chartLegend(.hidden)` | 300 pt | nothing |

The default legend for a continuous scale is the color ramp with its values,
and it costs 40 pt of plot height here.

## §9 Ground area of one cell

One hexagonal cell at longitude 172°,
its ground area integrated numerically on a sphere of radius 6,371 km:

| Latitude | Degree grid, radius 0.3° | East–west stretch | Equal-area grid, standard parallel 41° S | East–west stretch |
| --- | ---: | ---: | ---: | ---: |
| 34° S | 2,398 km² | ×0.83 | 2,890 km² | ×0.91 |
| 41° S | 2,183 km² | ×0.75 | 2,890 km² | ×1.00 |
| 48° S | 1,935 km² | ×0.67 | 2,890 km² | ×1.13 |

In degrees, a cell at 34° S covered 24 % more ground than one at 48° S,
and every cell was squashed east–west on the ground by 17–33 %.
After Lambert's cylindrical equal-area projection
(x = λ cos φ0, y = sin φ / cos φ0)
every cell covered the same ground,
and the stretch was 1 on the standard parallel.

## §10 Hexagons as areas in data space

Each cell drawn as `AreaMark(x:yStart:yEnd:series:)` at three x positions —
left edge, middle, right edge — so the shape is in data units:

| Chart | Result |
| --- | --- |
| One series for each cell, plot 480 × 360 | gap 0.0 %, overlap 0.0 % |
| One series for each cell, plot 480 × 300 | gap 0.0 %, overlap 0.0 % |
| Two cells with the same count, no series | joined into one area |
| Two cells with the same count, one series for each cell | two hexagons |

The cells tile at any plot size and ratio with no geometry reading.
Without a series, areas are grouped by their `foregroundStyle(by:)` value,
so cells with the same count are joined.

## §11 A size that follows the plot

The tiling chart sized from state that
`.onGeometryChange(for: CGSize.self) { $0.size } action: { … }`
inside `chartPlotStyle` writes:

| Run | Result |
| --- | --- |
| Hosted at 480 × 360, then resized to 240 × 180 | plot sizes reported: 480 × 360, then 240 × 180 |
| `ImageRenderer` at 480 × 360 | gap 0.0 %, overlap 0.0 % |
| Axes shown, `aspectRatio` and `clipped()` in `chartPlotStyle`, frame 480 × 480 | plot 463 × 348 pt, reported 463 × 347.2; gap 0.0 %, overlap 0.0 % |

The state follows a resize,
and `ImageRenderer` drew the settled size on its first pass,
so snapshot tests do not need the size injected.
The last row is the composition in `heatmap-code.md`.

## Not measured

- What VoiceOver reads for hexagon symbols or for area hexagons:
  the macOS accessibility tree was empty in the headless run.
- Rendering time and memory for large numbers of cells.
- Animation between data sets.
- Anything on a physical device or the iOS simulator.
