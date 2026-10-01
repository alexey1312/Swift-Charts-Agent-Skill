# Measured behavior

The skill's *Measured* statements come from `scripts/probes/masking_probe.swift`
in this repository.
Run it to re-derive every number below:

```bash
xcrun swiftc -O -suppress-warnings scripts/probes/masking_probe.swift -o "$TMPDIR/masking_probe"
"$TMPDIR/masking_probe" --png "$TMPDIR/masking-probe"   # --png also writes each render
```

**Setup.**
macOS 27.0 (26A428), Xcode 27.1 (27A9269), 2026-10-01.
Charts 400 × 240 pt with hidden axes and fixed scales,
rendered with `ImageRenderer` at 1× and compared pixel by pixel;
§3 and §4 host the chart in an offscreen `NSHostingView` to read its `ChartProxy`.
Seven daily points: 40, 70, 30, 95, 75, 55, 100.
Unless a line says otherwise, the x scale is the data's own range
with 16 pt of range padding each side —
`.chartXScale(domain: first…last, range: .plotDimension(startPadding: 16, endPadding: 16))` —
the configuration the article uses.

**Scope.**
Swift Charts is one framework on iOS and macOS,
and these are measurements of its layout, grouping and masking.
They were not repeated on an iOS simulator;
the hover gesture and the touch gesture differ, which is why §4 measures the
values a gesture can produce rather than a gesture.

## §1 Two copies of the same line

Two copies of the same seven points, drawn on top of each other.
"Joined" means ink at the middle of a straight segment from the last point back to
the first — a spot the data's own line does not cross.

| Layers | Result |
| --- | --- |
| `LinePlot` × 2, no `series:` | joined last → first |
| `LinePlot` × 2, distinct `series:` | not joined |
| `LinePlot` × 2, no `series:`, different constant colors | joined last → first |
| `LineMark` × 2 in `ForEach`, same `series:` | joined last → first |
| `LineMark` × 2 in `ForEach`, distinct `series:` | not joined |
| Two different collections (flat at 20 and at 80), no `series:` | joined into one line |
| Two different collections, distinct `series:` | two lines |
| Days 0–3 in one plot, days 4–6 dashed in another, no `series:` | one line, connected across the split, and the dashed half drawn solid |
| The same split, distinct `series:` | a gap between day 3 and day 4; the second half dashed |

It is not about copies.
Every line plot in a chart without a `series:` belongs to one series,
whatever data it holds,
and the merged line is drawn in one style — the dashed plot lost its dash.
Giving the halves their own series brings the dash back and opens a gap at the split;
two masked copies of the full data are what draw one continuous line in two styles
(`masking-code.md` › Actual and forecast).

A constant `foregroundStyle` does not separate series.
The *LineMark* documentation says marks without a series are grouped by their
foreground style or line style *value* — that is, by `foregroundStyle(by:)`,
not by a constant color.
Opacity was not varied here; nothing suggests it groups differently,
but that is untested.

## §2 Where the mask starts and ends

The line at width 5 with circle symbols (`symbolSize(150)`),
masked by a rectangle and compared with the same line unmasked.

| Mask | Pixels that differ | Lost left of the first point | Lost right of the last |
| --- | ---: | ---: | ---: |
| `RectangleMark` from the first point to the last | 102 | 68 | 29 |
| `RectanglePlot(data, …)`, same bounds | 102 | 68 | 29 |
| `RectangleMark(xStart: nil, xEnd: nil, yStart: nil, yEnd: nil)` | 0 | 0 | 0 |
| `RectangleMark` a week past the data each side, explicit domain | 0 | 0 | 0 |
| Domain padded by 12 h, no range padding, mask on the domain's bounds | 0 | — | — |

- A mask rectangle ends exactly at its x value.
  On a data point it cuts that point's symbol and line cap in half.
- `RectanglePlot` over the data with constant bounds masks the same pixels as one
  `RectangleMark`; it just draws seven rectangles.
- Masking to the plot's edges changes nothing,
  so a mask that runs to `domain.upperBound` when nothing is selected
  leaves the chart exactly as it was.

## §3 Marks outside the data and an automatic x domain

The x domain the chart chose, read with `ChartProxy.xDomain(dataType:)`,
with no `chartXScale` unless the row says so.

| Content | x domain |
| --- | --- |
| The line only | first point … last point |
| The line masked by a rectangle a week past the data each side | 168 h before the first point … 168 h after the last |
| The line and a `RuleMark` 18 h after the last point | first point … 18 h after the last |
| The same rule, explicit domain (first…last) | first point … last point |

Mask content and rules count toward an automatic domain like any other mark.
A selection rule that follows a raw value past the data
therefore rescales the whole chart while the person drags.
An explicit domain stops it.

## §4 What a selection can be

What `ChartProxy.value(atX:)` returns at a pointer position,
measured from the plot's leading edge:

| Position | Value |
| --- | --- |
| x = 0 pt, the plot's leading edge | 6.3 h before the first point |
| x = −30 pt, outside the plot | 18 h before the first point |
| x = 430 pt, outside the plot | 18 h after the last point |

`ChartProxy.selectXValue(at: -30)` — the call a custom `chartGesture` makes —
wrote **18 h before the first point** into the `chartXSelection(value:)` binding:
nothing clamps the value to the data or to the plot.
At the padded edge the first 16 pt of the plot are already outside the data.
Whether the built-in gesture reports positions beyond the plot during a drag
was not measured;
the conversion it relies on does not stop at the edge.

## §5 Gradient stops on unevenly spaced points

Points on days 0, 1, 5 and 6, colored red, green, blue and black
with a `LinearGradient` from leading to trailing, line width 20;
the color sampled on the line beside each point.
The x domain is padded by 12 hours each side,
so the plot area is wider than the line
and a gradient spanning the plot would land somewhere else than one spanning the line.

| Stops | Day 0 | Day 1 | Day 5 | Day 6 |
| --- | --- | --- | --- | --- |
| At evenly spaced indices (0, ⅓, ⅔, 1) | on color | off by 1.10 | off by 0.58 | on color |
| At each day's position between the first and last day | on color | on color | on color | on color |

"Off by" is the summed RGB distance from the intended color.
Index stops are right only when the points are evenly spaced.
Positions between the first and the last day land even with the padded domain,
so by default a line's gradient spans the line's own bounds, not the plot area
(`alignsMarkStylesWithPlotArea` is the documented switch to the plot area).

## Not measured

- What VoiceOver reads for a chart with a visible or hidden duplicate:
  the macOS accessibility tree was empty in the headless run.
  `CHART006` and the skill call that advice an *inference*.
- Animation of the mask edge, and drag performance with large data sets.
- Anything on a physical device or the iOS simulator.
