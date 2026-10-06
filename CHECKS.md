# Checks

Every automated rule in each skill's scanner, and the checks that need a person.
Matches are heuristics:
the agent reads the chart before a finding becomes a recommendation.
Each section's `measured-behavior.md` is that skill's own.

## swift-charts-dynamic-masking

### Automated — `charts_scan.py`

| Rule | Severity | Finds | Source |
| --- | --- | --- | --- |
| `CHART001` | high | Two line plots or marks of the same data whose `series:` is missing or equal — drawn as one line, joined from the last point back to the first | *LineMark* documentation; `measured-behavior.md` §1 |
| `CHART002` | medium | Data filtered or cut with `prefix(while:)` by the selection variable | *ChartContent.mask(content:)* documentation; `measured-behavior.md` §3 |
| `CHART003` | medium | A mask rectangle that starts on the first element, or falls back to the last — the edge symbols lose half their ink | `measured-behavior.md` §2 |
| `CHART004` | low | `RectanglePlot(data, …)` with constant bounds inside a mask — one rectangle per element where one `RectangleMark` does | `measured-behavior.md` §2; WWDC24 10155, 11:34 |
| `CHART005` | medium | The raw selection used as a mark's value with no clamp or snap — values past the data rescale an automatic domain | WWDC23 10037, 5:47; `measured-behavior.md` §3–4 |
| `CHART006` | low | More than one layer of the same data readable by VoiceOver (*inference*) | WWDC22 10137, 4:21; *ChartContent.accessibilityHidden(_:)* documentation |
| `CHART007` | medium | Layers of the same data with different interpolation methods | WWDC22 10137, 7:06 |
| `CHART008` | low | An annotation that formats the raw selection | WWDC23 10037, 5:47 |
| `CHART009` | info | A `DragGesture` in `chartOverlay` converted with `proxy.value(atX:)` — keep it only for iOS 16 | WWDC23 10037, 5:26 and 5:34 |
| `CHART010` | high | Line plots of different data in one chart, none with a `series:` — merged into one line in one style (a dashed plot loses its dash) | *LineMark* documentation; `measured-behavior.md` §1 |

The scanner also reports the iOS deployment targets it finds
(`IPHONEOS_DEPLOYMENT_TARGET`, `Package.swift` platforms)
and an inventory of the chart APIs in use.

#### Known limits

- Layers are matched by their data argument and their x and y key paths or
  properties. A `LineMark` inside `ForEach` has no data argument,
  so it is compared with every layer on the same x and y.
- `CHART003` follows an identifier one `let` back
  (`if let begin = days.first?.date`); deeper indirection is missed.
- `CHART005` accepts any `min`, `max` or `clamp` near an `onChange(of:)` of the
  selection as clamping.

### Manual

| Check | How |
| --- | --- |
| Selection states S1–S12 | `references/selection-state-matrix.md` |
| Every API above the deployment target is gated | `charts_sdk_check.py` against the scan's `ios_deployment_targets` |
| What VoiceOver reads | A run with VoiceOver; never measured by this repository |

## swift-charts-hexagonal-heatmap

### Automated — `heatmap_scan.py`

A *hexagon chart* is a `Chart` that draws a `ChartSymbolShape` named like a hexagon
or with six corners —
directly, or through a `ChartContent` type that does —
or that draws `AreaMark` bands inside nested `ForEach` loops.

| Rule | Severity | Finds | Source |
| --- | --- | --- | --- |
| `HEX001` | medium | A hexagon symbol sized by one area — `symbolSize(_ area:)` or `symbolSize(by:)` instead of a `CGSize` — which sets the height only and fits one axis | `measured-behavior.md` §1–3 |
| `HEX002` | high | A hexagon chart without `chartXScale(domain:)` and `chartYScale(domain:)` — the automatic domain includes zero | `measured-behavior.md` §4; WWDC22 10137, 13:41 |
| `HEX003` | low | A hexagon chart with no `clipped()` in `chartPlotStyle` — cells past the domain draw over the axes | `measured-behavior.md` §5 |
| `HEX004` | medium | `Dictionary(grouping:)`, or a function that counts into cells, called from `body` or a computed property of a view | WWDC24 10155, 12:02 and 12:14 |
| `HEX005` | medium | A function that converts to axial coordinates and rounds exactly two of them — q and r on their own | `measured-behavior.md` §6 |
| `HEX006` | low | `chartForegroundStyleScale` with a gradient range and a linear scale, stated or by default | `measured-behavior.md` §7 |
| `HEX007` | low | `.chartLegend(.hidden)` on a hexagon chart colored with `foregroundStyle(by:)` | `measured-behavior.md` §8; WWDC22 110340, 20:08 |
| `HEX008` | high | `AreaMark` bands in nested `ForEach` loops with no `series:` — cells with the same color value are joined | `measured-behavior.md` §10 |
| `HEX009` | low | `.aspectRatio` on a hexagon chart whose axes are shown, with no ratio in `chartPlotStyle` | `measured-behavior.md` §3; WWDC22 10137, 18:27 |

The scanner also reports the deployment targets, the hexagon shapes it found,
the files with hexagon charts, and an inventory of the APIs in use.

#### Known limits

- `HEX002`, `HEX003`, `HEX006` and `HEX007` read the whole file,
  so a modifier on another chart in the same file counts;
  a modifier in another file — a shared `ViewModifier` — does not.
- `HEX001` accepts a `symbolSize` argument as a `CGSize` when it is a `CGSize(…)`
  literal, a property declared as `CGSize`, or a call to a function that returns one.
- `HEX004` skips `.task`, `.onAppear`, `.onChange`, `.refreshable`, `.onReceive`
  and `Task` closures, and does not follow calls more than one function deep.
- `HEX005` takes a function as axial when it uses √3 or has `q:` and `r:` parameters;
  a conversion split over more functions is missed.
- `HEX008` does not judge `AreaPlot`,
  where a style value can legitimately group several bands.

### Manual

| Check | How |
| --- | --- |
| Heatmap states V1–V10 | `references/verification-matrix.md` |
| Every API above the deployment target is gated, `.symmetricLog` at iOS 16.4 | `heatmap_sdk_check.py` against the scan's `ios_deployment_targets` |
| What VoiceOver reads for each cell | A run with VoiceOver; never measured by this repository |
