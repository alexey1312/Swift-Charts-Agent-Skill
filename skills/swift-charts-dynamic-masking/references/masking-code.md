# Masking code

Every Swift block here is complete and was typechecked against the iOS 27.1 SDK
(Xcode 27.1, 27A9269) at the iOS version its first line names,
and fails one major version below it — that is how the availability claims were checked.
`tests/test_samples.py` repeats both checks;
a block marked *continues the block above* is compiled together with that block.
The renders described here come from macOS builds of the same code.

All examples plot one value per day.
Use your own model and key paths;
keep the structure.

## The scrub (iOS 18)

Everything up to the selected day at full strength,
everything after it dimmed,
a dashed rule and a popover on the selected day.
Rendered with the selection pinned between two days,
it snapped to the nearer one and dimmed the rest;
pinned three days past the end, it snapped to the last day
and the chart did not rescale.

```swift
// typecheck: ios18
import Charts
import SwiftUI

struct DailyTotal: Identifiable {
    let day: Date
    let minutes: Double
    var id: Date { day }
}

struct ScrubbedTrendChart: View {
    /// Sorted by `day`, oldest first.
    let totals: [DailyTotal]
    /// Raw value from the selection gesture. Marks never read it directly.
    @State private var rawSelection: Date?

    /// `initialSelection` lets previews and snapshot tests pin a selection state.
    init(totals: [DailyTotal], initialSelection: Date? = nil) {
        self.totals = totals
        _rawSelection = State(initialValue: initialSelection)
    }

    var body: some View {
        Chart {
            // 1. The whole line, dimmed; visible only while something is selected.
            LinePlot(totals, x: .value("Day", \.day), y: .value("Minutes", \.minutes),
                     series: .value("Layer", "Dimmed"))
                .interpolationMethod(.catmullRom)
                .opacity(selected == nil ? 0 : 0.25)
                .accessibilityHidden(true)

            // 2. The area under the active part.
            AreaPlot(totals, x: .value("Day", \.day), y: .value("Minutes", \.minutes))
                .interpolationMethod(.catmullRom)
                .opacity(0.3)
                .mask { activeRegion }
                .accessibilityHidden(true)

            // 3. The whole line again, masked to the active part. VoiceOver reads this copy.
            LinePlot(totals, x: .value("Day", \.day), y: .value("Minutes", \.minutes),
                     series: .value("Layer", "Active"))
                .interpolationMethod(.catmullRom)
                .mask { activeRegion }

            // 4. Selection feedback, placed on the matched element.
            if let selected {
                RuleMark(x: .value("Selected day", selected.day))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
                    .annotation(position: .top, overflowResolution: .init(x: .fit(to: .chart), y: .disabled)) {
                        VStack(alignment: .leading) {
                            Text(selected.day, format: .dateTime.weekday(.abbreviated))
                            Text(selected.minutes, format: .number.precision(.fractionLength(0)))
                        }
                        .font(.caption)
                    }
            }
        }
        .chartXScale(domain: domain)
        .chartXSelection(value: $rawSelection)
    }

    /// The element nearest the raw selection. Snapping also clamps: a selection past
    /// either end of the data snaps to the first or last element.
    private var selected: DailyTotal? {
        totals.nearest(to: rawSelection)
    }

    /// The data's range padded by half a day, in data units, so the first and last
    /// points sit inside the plot and the plot's edges are values a mask can use.
    private var domain: ClosedRange<Date> {
        guard let first = totals.first?.day, let last = totals.last?.day else {
            return Date.distantPast ... Date.distantFuture
        }
        return first.addingTimeInterval(-43_200) ... last.addingTimeInterval(43_200)
    }

    /// From the plot's leading edge to the selection, or the whole plot.
    private var activeRegion: some ChartContent {
        RectangleMark(
            xStart: .value("Start", domain.lowerBound),
            xEnd: .value("End", selected?.day ?? domain.upperBound)
        )
    }
}

extension [DailyTotal] {
    /// Binary search over elements sorted by `day`.
    func nearest(to date: Date?) -> DailyTotal? {
        guard let date, !isEmpty else { return nil }
        var low = startIndex, high = endIndex - 1
        while low < high {
            let middle = (low + high) / 2
            if self[middle].day < date { low = middle + 1 } else { high = middle }
        }
        if low > startIndex, date.timeIntervalSince(self[low - 1].day) < self[low].day.timeIntervalSince(date) {
            return self[low - 1]
        }
        return self[low]
    }
}
```

What each part is for:

- **`rawSelection` vs `selected`.**
  The binding gets the raw x value under the finger (WWDC23 10037, 5:47).
  Every mark reads `selected`, the nearest element,
  so nothing is ever drawn outside the data (`measured-behavior.md` §3–4).
  `nearest(to:)` was checked at both ends, past both ends, at a midpoint
  and on an empty array.
- **`domain`.**
  Half a day of padding in data units keeps the first and last symbols inside the
  plot, and makes the plot's edges values the mask can start and end on
  (`measured-behavior.md` §2).
  An empty array gets a placeholder domain rather than force-unwrapping.
- **`activeRegion`.**
  One `RectangleMark` with no y spans the plot's full height.
  With nothing selected it covers the whole plot,
  and the chart is pixel-identical to an unmasked one.
- **The dimmed copy** sits at opacity 0 rather than being removed,
  so the chart's content keeps the same structure as the selection comes and goes.

On iOS 17 the scrub needs marks instead of plots (*Marks and an overlay* below),
with `.chartXSelection(value: $rawSelection)` in place of the overlay.

## Pinning a state

Selection comes from a gesture, so a preview or a snapshot test cannot reach it —
unless the chart takes an initial value
(the scrub's `init(totals:initialSelection:)`).
The labels match `selection-state-matrix.md`.

```swift
// typecheck: ios18, continues the block above
import SwiftUI

#Preview("Selection states") {
    let start = Calendar.current.startOfDay(for: .now)
    let totals = [42.0, 68, 34, 91, 76, 57, 103].enumerated().map { index, minutes in
        DailyTotal(day: Calendar.current.date(byAdding: .day, value: index, to: start)!, minutes: minutes)
    }
    let day = { (offset: Double) in start.addingTimeInterval(offset * 86_400) }
    ScrollView {
        VStack(spacing: 24) {
            ScrubbedTrendChart(totals: totals)                                  // S1
            ScrubbedTrendChart(totals: totals, initialSelection: day(2.6))      // S3
            ScrubbedTrendChart(totals: totals, initialSelection: day(9))        // S7
        }
        .frame(height: 720)
        .padding()
    }
}
```

## Marks and an overlay (iOS 16 and 17)

`LinePlot`, `AreaPlot` and constant plot arguments are iOS 18.
Before that, each copy is a `ForEach` of marks,
and the whole `ForEach` takes the mask.
Rendered with the same data and selection,
it looked the same as the plot version (compared by eye).

```swift
// typecheck: ios16
import Charts
import SwiftUI

struct DailyTotal: Identifiable {
    let day: Date
    let minutes: Double
    var id: Date { day }
}

/// The same chart for iOS 16 and 17: marks instead of plots, and a drag gesture
/// in an overlay instead of `chartXSelection`.
struct ScrubbedTrendChartMarks: View {
    /// Sorted by `day`, oldest first.
    let totals: [DailyTotal]
    @State private var rawSelection: Date?

    var body: some View {
        Chart {
            ForEach(totals) { total in
                LineMark(x: .value("Day", total.day), y: .value("Minutes", total.minutes),
                         series: .value("Layer", "Dimmed"))
                    .interpolationMethod(.catmullRom)
                    .opacity(selected == nil ? 0 : 0.25)
                    .accessibilityHidden(true)
            }
            ForEach(totals) { total in
                AreaMark(x: .value("Day", total.day), y: .value("Minutes", total.minutes))
                    .interpolationMethod(.catmullRom)
                    .opacity(0.3)
                    .accessibilityHidden(true)
            }
            .mask { activeRegion }
            ForEach(totals) { total in
                LineMark(x: .value("Day", total.day), y: .value("Minutes", total.minutes),
                         series: .value("Layer", "Active"))
                    .interpolationMethod(.catmullRom)
            }
            .mask { activeRegion }
            if let selected {
                RuleMark(x: .value("Selected day", selected.day))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 3]))
            }
        }
        .chartXScale(domain: domain)
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle()
                    .fill(.clear)
                    .contentShape(Rectangle())
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { drag in
                                let origin = geometry[proxy.plotAreaFrame].origin
                                rawSelection = proxy.value(atX: drag.location.x - origin.x, as: Date.self)
                            }
                            .onEnded { _ in rawSelection = nil }
                    )
            }
        }
    }

    private var selected: DailyTotal? { totals.nearest(to: rawSelection) }

    private var domain: ClosedRange<Date> {
        guard let first = totals.first?.day, let last = totals.last?.day else {
            return Date.distantPast ... Date.distantFuture
        }
        return first.addingTimeInterval(-43_200) ... last.addingTimeInterval(43_200)
    }

    private var activeRegion: some ChartContent {
        RectangleMark(
            xStart: .value("Start", domain.lowerBound),
            xEnd: .value("End", selected?.day ?? domain.upperBound)
        )
    }
}

extension Array where Element == DailyTotal {
    func nearest(to date: Date?) -> DailyTotal? {
        guard let date, !isEmpty else { return nil }
        var low = startIndex, high = endIndex - 1
        while low < high {
            let middle = (low + high) / 2
            if self[middle].day < date { low = middle + 1 } else { high = middle }
        }
        if low > startIndex, date.timeIntervalSince(self[low - 1].day) < self[low].day.timeIntervalSince(date) {
            return self[low - 1]
        }
        return self[low]
    }
}
```

- On iOS 17, delete the `chartOverlay` and add `.chartXSelection(value: $rawSelection)`:
  the gesture, and hover on macOS, are then the framework's.
- `plotAreaFrame` is deprecated from iOS 17; `plotFrame` replaces it.

## Range highlight (iOS 18)

```swift
// typecheck: ios18
import Charts
import SwiftUI

struct DailyTotal: Identifiable {
    let day: Date
    let minutes: Double
    var id: Date { day }
}

/// Highlights a selected span. On iOS a range is selected with two fingers;
/// on macOS, by dragging (WWDC23 10037, 7:07).
struct RangeHighlightChart: View {
    /// Sorted by `day`, oldest first.
    let totals: [DailyTotal]
    @State private var rawRange: ClosedRange<Date>?

    var body: some View {
        Chart {
            LinePlot(totals, x: .value("Day", \.day), y: .value("Minutes", \.minutes),
                     series: .value("Layer", "Dimmed"))
                .opacity(span == nil ? 0 : 0.25)
                .accessibilityHidden(true)
            LinePlot(totals, x: .value("Day", \.day), y: .value("Minutes", \.minutes),
                     series: .value("Layer", "Active"))
                .mask {
                    RectangleMark(
                        xStart: .value("Start", span?.lowerBound.day ?? domain.lowerBound),
                        xEnd: .value("End", span?.upperBound.day ?? domain.upperBound)
                    )
                }
        }
        .chartXScale(domain: domain)
        .chartXSelection(range: $rawRange)
    }

    /// Both ends snapped to elements, so the highlight starts and ends on points.
    private var span: (lowerBound: DailyTotal, upperBound: DailyTotal)? {
        guard let rawRange,
              let lower = totals.nearest(to: rawRange.lowerBound),
              let upper = totals.nearest(to: rawRange.upperBound) else { return nil }
        return (lower, upper)
    }

    private var domain: ClosedRange<Date> {
        guard let first = totals.first?.day, let last = totals.last?.day else {
            return Date.distantPast ... Date.distantFuture
        }
        return first.addingTimeInterval(-43_200) ... last.addingTimeInterval(43_200)
    }
}

extension [DailyTotal] {
    func nearest(to date: Date?) -> DailyTotal? {
        guard let date, !isEmpty else { return nil }
        var low = startIndex, high = endIndex - 1
        while low < high {
            let middle = (low + high) / 2
            if self[middle].day < date { low = middle + 1 } else { high = middle }
        }
        if low > startIndex, date.timeIntervalSince(self[low - 1].day) < self[low].day.timeIntervalSince(date) {
            return self[low - 1]
        }
        return self[low]
    }
}
```

## Actual and forecast (iOS 18)

One line, solid up to a cutoff and dashed after it.
Two copies of all the data with complementary masks keep the curve continuous
across the cutoff.
Splitting the data into two plots does not:
without series they merge into one line in one style, the dash lost;
with series there is a gap at the cutoff (`measured-behavior.md` §1).
Rendered, the solid and dashed parts meet on the cutoff rule.

```swift
// typecheck: ios18
import Charts
import SwiftUI

struct DailyTotal: Identifiable {
    let day: Date
    let minutes: Double
    var id: Date { day }
}

/// One line, solid up to `cutoff` and dashed after it: two copies of the full data
/// with complementary masks, so the curve stays continuous across the cutoff.
struct ActualAndForecastChart: View {
    /// Recorded and forecast values together, sorted by `day`.
    let totals: [DailyTotal]
    let cutoff: Date

    var body: some View {
        Chart {
            LinePlot(totals, x: .value("Day", \.day), y: .value("Minutes", \.minutes),
                     series: .value("Part", "Forecast"))
                .interpolationMethod(.monotone)
                .lineStyle(StrokeStyle(lineWidth: 2, dash: [5, 4]))
                .mask { RectangleMark(xStart: .value("From", cutoff), xEnd: .value("To", domain.upperBound)) }
                .accessibilityHidden(true)
            LinePlot(totals, x: .value("Day", \.day), y: .value("Minutes", \.minutes),
                     series: .value("Part", "Actual"))
                .interpolationMethod(.monotone)
                .lineStyle(StrokeStyle(lineWidth: 2))
                .mask { RectangleMark(xStart: .value("From", domain.lowerBound), xEnd: .value("To", cutoff)) }
            RuleMark(x: .value("Today", cutoff))
                .foregroundStyle(.secondary)
        }
        .chartXScale(domain: domain)
    }

    private var domain: ClosedRange<Date> {
        guard let first = totals.first?.day, let last = totals.last?.day else {
            return Date.distantPast ... Date.distantFuture
        }
        return first.addingTimeInterval(-43_200) ... last.addingTimeInterval(43_200)
    }
}
```

A reveal-to-a-date animation is the same chart with the cutoff animated;
that was not rendered.

## Gradient stops by position (iOS 16)

```swift
// typecheck: ios16
import SwiftUI

/// A leading-to-trailing gradient with one stop per point, placed at the point's
/// position between the first and the last day -- the span a line's own bounds
/// cover. Stops spaced by index drift off the points when days are uneven.
func positionedGradient(days: [Date], colors: [Color]) -> LinearGradient {
    guard let first = days.first, let last = days.last, last > first else {
        return LinearGradient(colors: colors, startPoint: .leading, endPoint: .trailing)
    }
    let span = last.timeIntervalSince(first)
    let stops = zip(days, colors).map { day, color in
        Gradient.Stop(color: color, location: day.timeIntervalSince(first) / span)
    }
    return LinearGradient(stops: stops, startPoint: .leading, endPoint: .trailing)
}
```

Give the dimmed copy and the active copy the same gradient,
so their colors line up where the mask ends (`measured-behavior.md` §5).
