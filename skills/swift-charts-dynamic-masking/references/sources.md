# Sources

Cite the session and timestamp, the documentation page,
or the section of `measured-behavior.md` a recommendation rests on.
Timestamps are where the passage starts in Apple's published transcript.
When a sample and the SDK disagree, the SDK wins (`api-availability.md`).

## Explore pie charts and interactivity in Swift Charts — WWDC23 10037

<https://developer.apple.com/videos/play/wwdc2023/10037/>

| Time | Takeaway |
| --- | --- |
| 5:26 | `chartOverlay` is the older way to capture gestures, with an overlaid view. |
| 5:34 | `chartXSelection` (iOS 17) recognizes the gesture itself and stores the selected value in a binding. |
| 5:47 | The binding holds the raw x value; a computed property matches it to a data point. |
| 6:03 | A vertical `RuleMark` marks the selected value. |
| 6:09 | A negative `zIndex` keeps that rule behind the lines. |
| 6:16 | The popover is an annotation with a custom SwiftUI view. |
| 6:32–6:48 | `overflowResolution`: fit to the chart on x, disabled on y, so the popover can sit above the plot. |
| 6:59 | On macOS the default selection gesture is hover. |
| 7:07–7:18 | `chartXSelection(range:)`: two fingers on iOS, a drag on macOS. |
| 7:21 | A custom selection gesture can select values through `ChartProxy`. |

The talk does not say how often the binding updates during a drag.

## Swift Charts: Vectorized and function plots — WWDC24 10155

<https://developer.apple.com/videos/play/wwdc2024/10155/>

| Time | Takeaway |
| --- | --- |
| 0:51 | Vectorized plots draw larger data sets more efficiently. |
| 2:36 | Charts are accessible by default; VoiceOver and Audio Graph work on plots too. |
| 10:21 | Modifiers on vectorized plots take key paths. |
| 11:34 | Use plots for large, uniformly styled data. |
| 11:45 | Use marks for fewer points with per-element styling, or when you need `zIndex` layering. |
| 12:02 | Performance: group data by style, precompute values, give known styles and bounds. |

## Swift Charts: Raise the bar — WWDC22 10137

<https://developer.apple.com/videos/play/wwdc2022/10137/>

| Time | Takeaway |
| --- | --- |
| 4:21 | VoiceOver elements are generated for chart data by default. |
| 7:06 | Interpolation method set per mark. |
| 8:23 | `AreaMark` from a start to an end value. |
| 9:31 | `RuleMark` for a reference value, with an annotation at 9:38. |
| 19:17 | `ChartProxy` converts between data values and positions. |
| 19:52 | `chartOverlay` and `chartBackground` provide the proxy. |
| 20:22–20:47 | A `DragGesture` location minus the plot area's origin, converted to a date range in `@State`. |
| 20:51 | A `RectangleMark` shows the selected range. |

## Hello Swift Charts — WWDC22 10136

<https://developer.apple.com/videos/play/wwdc2022/10136/>

| Time | Takeaway |
| --- | --- |
| 7:24 | VoiceOver reads the chart's data. |
| 16:16 | Dark Mode, Dynamic Type, VoiceOver and Audio Graphs come for free. |

## Apple documentation

All under <https://developer.apple.com/documentation/>.

- `charts/linemark` — marks with the same `series` value are drawn as one line;
  without a series, marks are grouped by their foreground or line style value.
- `charts/linemark/init(x:y:series:)` — a separate line per unique series value.
- `charts/chartcontent/mask(content:)` — masks chart content with the alpha
  channel of the content you pass.
- `charts/chartcontent/accessibilityhidden(_:)` — hides chart content from
  accessibility features.
- `charts/chartcontent/alignsmarkstyleswithplotarea(_:)` — aligns a mark's styles
  with the plot area instead of the mark.
- `swiftui/view/chartxselection(value:)`, `swiftui/view/chartxselection(range:)` (iOS 17).
- `charts/chartproxy/selectxvalue(at:)`, `swiftui/view/chartgesture(_:)` (iOS 17).
- `charts/chartproxy` — obtained from `chartOverlay` or `chartBackground`,
  converts between data values and screen coordinates.
- `charts/positionscalerange/plotdimension(startpadding:endpadding:)` —
  a range that fills the plot, with padding in points.
- `charts/lineplot` (iOS 18) — a whole collection or a function as one line.

## The article

Anton Gubarenko,
[*SwiftUI Charts: Dynamic Masking*](https://antongubarenko.substack.com/p/swiftui-charts-dynamic-masking)
(2026-09-22),
builds the scrub in eight steps — line, area, selection, rule and annotation,
clamping, a `RectanglePlot` mask, a dimmed copy, separate series —
and credits Natalia Panferova and Matthaus Woolard's book
*Swift Charts Beyond the Basics* for the masking idea.
This skill keeps the composition and rewrites the code.
Where the probe measured something the article does not mention,
the skill follows the measurement:

| Article | This skill | Why |
| --- | --- | --- |
| Mask from the first data point, falling back to the last | Mask from the domain's lower bound to its upper bound | `measured-behavior.md` §2: the first and last symbols are cut in half |
| `RectanglePlot` over the data as the mask | One `RectangleMark` | §2: same pixels, one rectangle instead of one per element |
| Clamp the raw selection in `onChange` | Snap it to the nearest element; marks read only that | §3–4, and the annotation then reads one element |
| Popover date from the raw selection, value from the nearest element | Both from the nearest element | the date can name the neighbouring day |
| Dimmed copy readable by VoiceOver | Dimmed copy and area hidden | WWDC22 10137 4:21 (*inference*) |
| Gradient stops by index | Stops by x position | §5: index stops drift with uneven spacing |

The series fix and the shared interpolation method are the article's,
and the probe confirms the first (§1).
