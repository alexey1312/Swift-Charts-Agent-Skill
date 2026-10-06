# Sources

Cite the session and timestamp, the documentation page,
or the section of `measured-behavior.md` a recommendation rests on.
Timestamps are where the passage starts in Apple's published transcript.
When a sample and the SDK disagree, the SDK wins (`api-availability.md`).

## Swift Charts: Raise the bar — WWDC22 10137

<https://developer.apple.com/videos/play/wwdc2022/10137/>

| Time | Takeaway |
| --- | --- |
| 4:25–4:45 | VoiceOver gets generated elements for chart data; `accessibilityLabel` and `accessibilityValue` customize them. |
| 6:36–6:45 | `foregroundStyle(by:)` picks the colors and adds a legend to say what each color means. |
| 10:08 | A heat map is one of the charts built by composing marks. |
| 12:55–13:07 | A scale maps data values to a mark property, such as x position or color. |
| 13:41–13:57 | Swift Charts infers scales from the data; the example's y scale came out as zero to 150. |
| 14:13 | `chartYScale(domain:)` fixes the domain. |
| 14:26 | `chartForegroundStyleScale` changes how values map to colors. |
| 14:44–14:56 | Axes and legends help people interpret a chart; the plot area is where the marks go. |
| 17:51–18:07 | Hide the legend only when something else already says what the colors mean. |
| 18:12–18:45 | `chartPlotStyle` configures the plot area, for example an exact size or aspect ratio. |
| 19:17–19:31 | `ChartProxy` converts between data values and positions. |

## Swift Charts: Vectorized and function plots — WWDC24 10155

<https://developer.apple.com/videos/play/wwdc2024/10155/>

| Time | Takeaway |
| --- | --- |
| 0:51 | Vectorized plots draw larger data sets more efficiently. |
| 7:16–7:32 | Vectorized plots handle a whole collection; a scatter plot and a heatmap are the examples. |
| 9:02–9:14 | Raw longitude and latitude are projected (Albers) before they are plotted on a flat surface. |
| 9:14–9:37 | Stored properties, not computed ones, let the chart read x and y at a constant offset. |
| 9:43 | `PointPlot` takes an entire collection. |
| 10:21–10:32 | Modifiers on vectorized plots take key paths, `symbolSize` among them. |
| 11:34 | Use plots for large data styled the same way. |
| 11:45 | Use marks for fewer points with per-element styling, or for `zIndex` layering. |
| 12:02–12:19 | Group data by style; avoid computations during rendering, such as computed properties. |
| 12:26 | Known styles and known bounds make a chart render more efficiently. |

## Design an effective chart — WWDC22 110340

<https://developer.apple.com/videos/play/wwdc2022/110340/>

| Time | Takeaway |
| --- | --- |
| 17:18–18:14 | Good accessibility labels are short, spell words out, and put the context value first. |
| 18:38–19:20 | Labels follow the chart's goal; a chart with too many marks to visit one by one can label sections. |
| 19:52 | Color can communicate intensity, such as heat in a weather forecast. |
| 20:08 | Color should add to a chart, not be the only way it conveys critical information. |
| 21:35–21:44 | Colors must adapt to Dark Mode, Light Mode and Increase Contrast. |
| 23:11–23:21 | Colors must contrast with each other and with the background. |

## Apple documentation

All under <https://developer.apple.com/documentation/>.

- `charts/chartsymbolshape/perceptualunitrect` — the rectangle that bounds the shape
  so that viewers perceive it as the size and position of a unit rectangle.
- `charts/scaletype/symmetriclog(slopeatzero:)` (iOS 16.4) — a symmetric log scale;
  `slopeAtZero` is a positive constant that controls the slope at zero.
- `swiftui/view/chartplotstyle(content:)` — configures the size or aspect ratio
  of the plot area.
- `charts/pointplot` (iOS 18) — a whole collection as points.
- `charts/linemark` — marks with the same `series` value are drawn as one line;
  without a series, marks are grouped by their foreground or line style value.
- `charts/chartcontent/accessibilityhidden(_:)` — hides chart content from
  accessibility features.

## The article

Matthaus Woolard,
[*Visualising data with a hexagonal heatmap in Swift Charts*](https://nilcoalescing.com/blog/VisualisingDataWithAHexagonalHeatmapInSwiftCharts/)
(Nil Coalescing, 2026-09-27),
plots 53,763 earthquakes across New Zealand from the GeoNet catalogue:
axial coordinates and cube rounding to bin them,
`PointPlot` at each occupied cell's center,
a custom `ChartSymbolShape` hexagon with a narrow `perceptualUnitRect`,
a symbol area computed from the plot's width,
`foregroundStyle(by:)` with a `.symmetricLog` gradient,
and a coastline drawn with `LinePlot`.
Its gist adds the coastline and a view modifier that resizes the hexagons.
The article and the gist carry no licence;
this skill keeps the technique and writes its own code.
Where the probe measured something the article does not mention,
the skill follows the measurement:

| Article | This skill | Why |
| --- | --- | --- |
| Symbol area = (cell width)² × 0.92, "a small visual separation" | `symbolSize(CGSize)` from each axis's scale, or area = (cell height)² | `measured-behavior.md` §1–2: the area sets the height, so the article's cells are 83 % size and 29 % of the plot is gap |
| `.aspectRatio` on the whole chart | `aspectRatio` inside `chartPlotStyle` | §3: with axes shown, the chart's ratio is not the plot's |
| The first `Hexagon` has only `path(in:)` | Every `ChartSymbolShape` declares `perceptualUnitRect` | SDK: the property is required; the first version does not compile |
| No clipping | `.chartPlotStyle { $0.clipped() }` | §5: cells past the domain draw over the axes |
| Legend hidden in the gist | Legend kept | §8: it is the color bar with values; WWDC22 110340 20:08 |
| Bins in longitude and latitude, "an equal-area projection may be more appropriate" | A cylindrical equal-area projection before binning, when ground area matters | §9: degree cells vary by 24 % in area across New Zealand |
| `symmetricLog` without a version | `symmetricLog` is iOS 16.4 | SDK; `api-availability.md` |

Kept from the article, and confirmed:
axial coordinates with cube rounding (§6: independent rounding put 16.8 % of points
in the wrong cell),
explicit domains with `plotDimension(padding: 0)` (§3–4),
a narrow `perceptualUnitRect` when sizing by area (§1),
and `.symmetricLog` for skewed counts (§7).
The article credits its book *Swift Charts Beyond the Basics*
(Natalia Panferova and Matthaus Woolard) for deeper material.
