# API availability

Before writing chart code, check what the selected SDK declares and since when:

```bash
python3 scripts/heatmap_sdk_check.py                       # iOS device SDK
python3 scripts/heatmap_sdk_check.py --platform iphonesimulator
python3 scripts/heatmap_sdk_check.py --format json         # includes each declaration line
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
   for this skill, `ForEach` and `PointMark` (`heatmap-code.md`).
3. **Check the point release.**
   `ScaleType.symmetricLog` is iOS **16.4**, not 16.0:
   a deployment target of iOS 16.0 to 16.3 needs a gate.
4. **Say which toolchain you checked.**
   Report `xcodebuild -version` and the SDK version next to an availability claim.

## Measured snapshot

iOS 27.1 SDK, Xcode 27.1 (27A9269), and iOS 27.0 SDK, Xcode 27.0 (27A266a), 2026-10-06:
the same versions in both.
Every code block in `heatmap-code.md` was also compiled at the iOS version it is
tagged with and failed one release below,
which checks the versions that matter here a second way.

| API | iOS | Notes |
| --- | --- | --- |
| `PointMark(x:y:)` | 16 | in `ForEach`; the same pixels as `PointPlot` |
| `ChartSymbolShape` | 16 | `perceptualUnitRect` is a requirement with no default |
| `ChartContent.symbol(_:)` | 16 | returns plain chart content |
| `ChartContent.symbolSize(_ area: CGFloat)`, `symbolSize(_ size: CGSize)` | 16 | the `CGSize` form sets width and height |
| `View.chartSymbolSizeScale(domain:range:type:)` | 16 | |
| `ChartContent.foregroundStyle(by:)` | 16 | |
| `View.chartForegroundStyleScale(domain:range:type:)` | 16 | a `Gradient` is a `ScaleRange` since iOS 16 |
| `ScaleType.symmetricLog`, `.symmetricLog(slopeAtZero:)` | **16.4** | also `.power(exponent:)` and `.squareRoot` |
| `View.chartLegend(_:)` | 16 | |
| `View.chartXScale(domain:range:)`, `.plotDimension(padding:)` | 16 | |
| `View.chartPlotStyle(content:)` | 16 | |
| `View.onGeometryChange(for:of:action:)`, one-value action | 16 | SwiftUI; back-deployed |
| `View.onGeometryChange(for:of:action:)`, old-and-new action | 18 | |
| `AreaMark(x:yStart:yEnd:series:)` | 16 | |
| `ChartContent.accessibilityLabel(_:)`, `.accessibilityValue(_:)` with a string | 16 | |
| `ChartContent.accessibilityHidden(_:)` | 16 | |
| `PointPlot(_:x:y:)` | 18 | vectorized |
| `LinePlot(_:x:y:series:)`, `AreaPlot(_:x:yStart:yEnd:series:)` | 18 | |
| Key-path `symbolSize(by:)`, `accessibilityLabel(_:)`, `accessibilityValue(_:)` | 18 | on vectorized plots |

`onGeometryChange` is in SwiftUI, so `heatmap_sdk_check.py` does not report it;
the iOS 16 blocks in `heatmap-code.md` call it and compile at iOS 16.

**Order of modifiers on a plot.**
`symbol(_:)` and a constant `symbolSize(_:)` return plain chart content,
which has no key-path modifiers.
Put `foregroundStyle(by:)`, `accessibilityLabel(_:)` and the other key-path modifiers
before them.
In the other order, `swiftc` does not name the missing overload:
it reports that it cannot type-check the expression in reasonable time.

The `symmetricLog` floor, compiled:
this block compiles for iOS 16.4 and fails for iOS 16.3.

```swift
// typecheck: ios16.4
import Charts
import SwiftUI

struct CountColors: ViewModifier {
    let maximum: Int

    func body(content: Content) -> some View {
        content.chartForegroundStyleScale(
            domain: 0 ... maximum,
            range: Gradient(colors: [.blue.opacity(0.12), .red]),
            type: .symmetricLog(slopeAtZero: 1)
        )
    }
}
```

So, by deployment target:

- **iOS 18 and later** — `PointPlot` with key paths, `.symmetricLog` as written
  (`heatmap-code.md` › The heatmap with a vectorized plot).
- **iOS 16.4 to 17** — `ForEach` and `PointMark`; `.symmetricLog` without a gate.
- **iOS 16.0 to 16.3** — the same, and `.symmetricLog` behind `if #available(iOS 16.4, *)`,
  with a linear scale over log(1 + count) as the fallback (`measured-behavior.md` §7).
