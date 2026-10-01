# API availability

Before writing chart code, check what the selected SDK declares and since when:

```bash
python3 scripts/charts_sdk_check.py                       # iOS device SDK
python3 scripts/charts_sdk_check.py --platform iphonesimulator
python3 scripts/charts_sdk_check.py --format json         # includes each declaration line
```

The script reads `Charts.swiftinterface` — the file the compiler uses —
and reports the iOS version in each declaration's `@available` attribute,
or in the attribute of the type or extension that declares it.
It changes nothing.

## Rules

1. **The SDK is the ground truth.**
   A blog post's or a session's sample is a snapshot.
   If it disagrees with the SDK, write what the SDK declares and say so.
2. **The deployment target decides the shape of the code.**
   An API above the target needs `if #available(iOS <version>, *)` and a fallback,
   or the older construction in its place —
   for this skill, marks and an overlay gesture (`masking-code.md`).
3. **Say which toolchain you checked.**
   Report `xcodebuild -version` and the SDK version next to an availability claim.

## Measured snapshot

iOS 27.1 SDK, Xcode 27.1 (27A9269), 2026-10-01.
Every code block in `masking-code.md` was also compiled at the iOS version it is
tagged with and failed one major version below,
which checks the versions that matter here a second way.

| API | iOS | Notes |
| --- | --- | --- |
| `LineMark`, `AreaMark`, `RuleMark`, `RectangleMark` | 16 | `LineMark(x:y:series:)` is iOS 16 too |
| `RectangleMark(xStart:xEnd:yStart:yEnd:)` with no y | 16 | one rectangle, the plot's full height |
| `ChartContent.mask(content:)` | 16 | |
| `ChartContent.opacity(_:)`, `.interpolationMethod(_:)`, `.accessibilityHidden(_:)` | 16 | |
| `ChartContent.alignsMarkStylesWithPlotArea(_:)` | 16 | |
| `View.chartOverlay`, `ChartProxy.value(atX:as:)` | 16 | the iOS 16 selection route |
| `ChartProxy.plotAreaFrame` | 16 | deprecated in iOS 17 — use `plotFrame` |
| `View.chartXScale(domain:range:)`, `.plotDimension(startPadding:endPadding:)` | 16 | |
| `View.chartXSelection(value:)` and `(range:)` | 17 | |
| `View.chartGesture(_:)`, `ChartProxy.selectXValue(at:)` | 17 | |
| `ChartProxy.plotFrame` | 17 | |
| `annotation(…, overflowResolution:)` | 17 | |
| `ChartContent.zIndex(_:)` | 17 | |
| `LinePlot`, `AreaPlot`, `RectanglePlot` | 18 | vectorized plots |
| `LinePlot(_:x:y:series:)` | 18 | |
| Constant `PlottableProjection.value(_:_:)` | 18 | `series: .value("Layer", "Dimmed")` in a plot |

So, by deployment target:

- **iOS 18 and later** — the scrub as written (`masking-code.md` › The scrub).
- **iOS 17** — marks instead of plots, `chartXSelection` for the gesture.
- **iOS 16** — marks, and a `DragGesture` in `chartOverlay`.
