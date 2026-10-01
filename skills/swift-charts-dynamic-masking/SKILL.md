---
name: swift-charts-dynamic-masking
description: >-
  Use this skill when a Swift Charts chart should show part of its data at full
  strength and the rest dimmed or hidden: the TradingView-style scrub that keeps
  everything left of the finger bright, a selected range highlighted, actual
  versus forecast drawn from one line, a reveal up to a date. Also use it for the
  parts that effect is built from — chartXSelection and snapping its value,
  RuleMark and annotation for the selection, ChartContent.mask with
  RectangleMark, layered LinePlot / AreaPlot or LineMark copies and their
  series — and for the bugs they cause: a diagonal line joining the end of a
  chart back to its start, half-cut first and last points, a chart that rescales
  while dragging, a tooltip naming the wrong day, data filtered on every drag.
  iOS 16 to the current SDK. Not for picking a chart type, axis or legend
  styling, pie charts, Chart3D, scrolling charts, or charts drawn without Swift
  Charts.
---

# Swift Charts dynamic masking

Never change the data to show part of it.
Plot complete copies of the same data and change only what a mask reveals
and how opaque each copy is.
The selection then moves one rectangle edge and one opacity;
the marks, the scales and the chart's geometry stay put.

Anton Gubarenko's article *SwiftUI Charts: Dynamic Masking* builds this effect
step by step (`references/sources.md`).
This skill keeps its composition, changes the parts the repository's probe
found drawing wrong, and grounds every rule in Apple's sessions, the documentation,
the SDK, or that measurement.

- Code that compiles: `references/masking-code.md`
- What was measured, and how: `references/measured-behavior.md`
- Which API needs which iOS: `references/api-availability.md`
- States to verify: `references/selection-state-matrix.md`
- Plan format: `references/recommendation-format.md`
- Citations: `references/sources.md`

## Contract

- **Phase 1 is read-only.**
  Scanning, checking the SDK, reading code and writing the plan change nothing.
- **No edits without approval of item IDs** (`references/recommendation-format.md`).
  "Make the chart do the TradingView thing" before a plan exists is a request for the plan.
- **The SDK and the deployment target decide what can be written.**
  `LinePlot` and `AreaPlot` need iOS 18, `chartXSelection` iOS 17;
  below that there is a marks-and-overlay version, not a guess.
- **Cite a source for every item:** a session and timestamp, a documentation page,
  or a section of `measured-behavior.md`.
  Anything else is labelled *inference*.
- **Report verification honestly.**
  A green build proves it compiles.
  Only a rendered state — a preview, a snapshot, a run — proves how it looks,
  and only for the states actually rendered.

## 1. The composition

Bottom to top, in declaration order:

| Layer | Data | `series:` | Mask | Opacity | VoiceOver |
| --- | --- | --- | --- | --- | --- |
| Dimmed line | all | `"Dimmed"` | none | 0 with no selection, about 0.25 with one | hidden |
| Area | all | — | active region | about 0.3 | hidden |
| Active line | all | `"Active"` | active region | 1 | reads this copy |
| Rule and annotation | the matched element | — | none | — | — |

- **Every copy gets the same x, y and interpolation method**,
  or the bright part drifts off the dim one (scanner `CHART007`).
- **Every line copy gets its own `series:`.**
  Marks with the same series are drawn as one line (*LineMark* documentation),
  and two copies without a series are one series:
  Swift Charts joins the end of the first back to the start of the second.
  A different constant color does not separate them
  (*Measured* §1; scanner `CHART001`).
  The same goes for any two line plots in a chart, whatever their data:
  a solid half and a dashed half without series drew as one solid line
  (*Measured* §1; `CHART010`).
- **Keep one copy readable.**
  Charts make accessibility elements for their data by default
  (WWDC22 10137, 4:21),
  so mark the dimmed copy and the area `.accessibilityHidden(true)`
  (*inference* — VoiceOver output was not measured; `CHART006`).
- **Layering is declaration order.**
  Vectorized plots are for large, uniformly styled data;
  use marks when you need `zIndex` layering (WWDC24 10155, 11:34 and 11:45).
  The selection talk keeps its `RuleMark` behind the lines with a negative `zIndex`
  (WWDC23 10037, 6:09; `zIndex` is iOS 17).

## 2. The mask

- **`ChartContent.mask(content:)` takes chart content** (iOS 16),
  so the mask is drawn in data space: `RectangleMark(xStart:xEnd:)` with no y
  spans the plot's full height.
  No pixel conversion, no `GeometryReader`.
- **One `RectangleMark`, not `RectanglePlot(data, …)`.**
  A plot with constant bounds draws one identical rectangle per element;
  the masked pixels are the same (*Measured* §2; `CHART004`).
- **Start the mask at the plot's edge, not at the first point.**
  A rectangle ends exactly at its x value,
  so a mask from the first point cuts away the left half of that point's symbol
  and line cap — 68 px in the probe — and a mask that falls back to the last point
  cuts the right half of the last one (*Measured* §2; `CHART003`).
  Pad the x domain in data units (half the spacing between points)
  and mask from `domain.lowerBound` to the selection,
  or to `domain.upperBound` when nothing is selected:
  0 px differ from the unmasked chart.
- **Keep the mask inside an explicit domain.**
  Mask marks count toward an automatic x domain:
  a mask a week past the data widened the domain by a week each side
  (*Measured* §3).
  Range padding (`.plotDimension(startPadding:endPadding:)`) with a mask that starts
  well before the data also works, but only because the domain is explicit.
- The mask's edge splits the selected point's symbol — that is the effect.
- **A hard-stop gradient is the one-layer alternative** when only opacity changes:
  one copy whose `LinearGradient` has two stops at the cutoff's position between
  the first and the last point.
  Stops placed by position land on their points (*Measured* §5);
  the hard stop itself is *inference*, not measured.
  A gradient cannot change dash, width or symbols past the cutoff — that needs masks.

## 3. Selection

- **`chartXSelection(value:)`** (iOS 17) recognizes the gesture and writes the
  selected x value to a binding;
  `chartOverlay` with a gesture is the older route (WWDC23 10037, 5:26 and 5:34).
  On macOS the default selection gesture is hover (6:59):
  the dimming follows the pointer with no click.
  What the binding holds after the finger lifts was not measured here and the talk
  does not say; verify it (state S8) before promising either behavior.
- **The binding holds the raw value; match it to a data point**
  (WWDC23 10037, 5:47).
  The raw value leaves the data: at the plot's padded edge it was 6.3 hours before
  the first point, and a pointer 30 pt outside the plot gave 18 hours
  (*Measured* §4).
  Snap it to the nearest element — a binary search over sorted data —
  and snapping clamps for free.
- **Marks read only the snapped element.**
  A `RuleMark` at a raw value past the data widens an automatic domain,
  so the whole chart rescales mid-drag (*Measured* §3; `CHART005`).
  Give the chart an explicit `chartXScale(domain:)` either way.
- **The annotation reads one element.**
  Formatting the raw selection beside a value from the nearest element labels one
  point with another's date: past the midpoint between two days the value comes
  from the next day while the label still names the previous one (`CHART008`).
- **Indicator and popover:** a `RuleMark` (6:03) with an annotation
  (6:16) whose `overflowResolution` fits x to the chart and disables y,
  so it can sit above the plot (6:32–6:48; iOS 17).
- **Ranges:** `chartXSelection(range:)` — two fingers on iOS, a drag on macOS
  (7:07–7:18). Snap both ends; the mask runs from one to the other.
- **iOS 16:** a `DragGesture` in `chartOverlay`,
  subtracting the plot frame's origin before `proxy.value(atX:)`
  (WWDC22 10137, 19:17–20:47).
  `plotAreaFrame` is deprecated from iOS 17 in favor of `plotFrame`;
  at an iOS 16 deployment target it compiles without a warning,
  and from iOS 17 the compiler warns (checked with `swiftc -typecheck`).
- **Never filter the data to the selection** (`CHART002`):
  it rebuilds every mark per drag event and, with an automatic domain,
  rescales the chart as the slice shrinks.

## 4. Plots or marks

- **iOS 18 and later:** `LinePlot` and `AreaPlot` take the whole collection
  and key paths (WWDC24 10155, 0:51 and 10:21) and suit this effect,
  whose copies are uniformly styled.
  Constant plot arguments such as `series: .value("Layer", "Dimmed")` are iOS 18 too.
- **iOS 16 and 17:** `ForEach` with `LineMark(x:y:series:)` and `AreaMark`,
  each `ForEach` masked as a whole.
  Rendered on macOS, it looked the same as the plot version
  (compared by eye, not by the committed probe).
- **Gradients:** place stops at each point's x position, not at evenly spaced
  indices — with uneven spacing, index stops put the wrong color on the points
  (*Measured* §5).
  Both copies take the same style, so their colors line up.

## 5. The same technique elsewhere

`references/masking-code.md` has each one compiled:

- **Range highlight** — mask from the snapped lower bound to the snapped upper bound.
- **Actual and forecast** — one line, two copies with complementary masks
  (solid to the cutoff, dashed after it), so the curve stays continuous at the cutoff.
  Two plots of the two halves either merge into one solid line (no series)
  or leave a gap at the cutoff (distinct series) — *Measured* §1.
- **Reveal to a date** — the scrub with a fixed date instead of a selection.

## Workflow

### Phase 1 — Recommend

1. **Preflight.**
   `xcodebuild -version`; the app's deployment target
   (the scan reports `ios_deployment_targets`); the project's own agent
   instructions (`AGENTS.md`, `CLAUDE.md`).
   Report the toolchain in the plan.
   Where `xcodebuild` cannot run (a sandbox that blocks its cache),
   `xcrun --sdk iphoneos --show-sdk-version` and the header of `charts_sdk_check.py`
   still name the SDK — report those, and say `xcodebuild` was unavailable.
2. **Scan and check:**

   ```bash
   python3 scripts/charts_scan.py <project-root> --format json > "$TMPDIR/charts-scan.json"
   python3 scripts/charts_scan.py <project-root> --format markdown
   python3 scripts/charts_sdk_check.py      # iOS floor of every API below
   ```

   The scan skips dependencies and hidden directories.
   Its matches are heuristics: read the chart before a finding becomes an item.
3. **Plan** with `references/recommendation-format.md`:
   correctness first (`CHART001`, `003`, `005`, `007`, `008`, `010`),
   then the technique itself (replace slicing or a hand-rolled gesture),
   then polish (`CHART004`, `006`, gradients, the popover).
   Mark anything above the deployment target with the gate it needs,
   or plan the marks-and-overlay version.
4. **Ask** which item IDs to apply.

### Phase 2 — Apply and verify

1. Apply approved items only, one group at a time; change only the lines they name.
2. Build with the project's own command after each group.
3. Re-run `charts_scan.py`; the resolved findings should be gone.
4. Verify the states in `references/selection-state-matrix.md` that the change touches.
   Give the chart an `initialSelection` parameter
   (`references/masking-code.md` › Pinning a state)
   so previews and snapshot tests can render each state without a gesture.
   States not rendered are reported as *not verified*.
5. Update each item's status and hand back the report.

## Guardrails

- Do not slice, filter or rebuild the data on selection.
- Do not mask the whole `Chart` view with a SwiftUI `.mask` or `.clipShape`:
  that masks axes and gridlines too, and needs plot coordinates the chart
  already has (*inference*).
- Do not write `LinePlot`, `AreaPlot` or constant `PlottableProjection` values
  below iOS 18, or `chartXSelection` below iOS 17, without an `if #available` gate.
- Snapshot references move when layers, masks or padding change;
  say which ones and why rather than re-recording blind.
