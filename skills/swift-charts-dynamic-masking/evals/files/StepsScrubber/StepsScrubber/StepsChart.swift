import Charts
import SwiftUI

struct StepCount: Identifiable {
    let id = UUID()
    let day: Date
    let steps: Int
}

struct StepsChart: View {
    let counts: [StepCount]
    @State private var scrubbed: Date?

    private var range: ClosedRange<Date> {
        (counts.first?.day ?? .now) ... (counts.last?.day ?? .now)
    }

    var body: some View {
        Chart {
            LinePlot(counts, x: .value("Day", \.day), y: .value("Steps", \.steps))
                .interpolationMethod(.monotone)
                .lineStyle(StrokeStyle(lineWidth: 4))
                .symbol(.circle)
                .opacity(scrubbed == nil ? 0 : 0.2)

            LinePlot(counts, x: .value("Day", \.day), y: .value("Steps", \.steps))
                .interpolationMethod(.monotone)
                .lineStyle(StrokeStyle(lineWidth: 4))
                .symbol(.circle)
                .mask {
                    if let start = counts.first?.day, let end = counts.last?.day {
                        RectangleMark(xStart: .value("Start", start), xEnd: .value("End", scrubbed ?? end))
                    }
                }
                .accessibilityHidden(false)
        }
        .chartXSelection(value: $scrubbed)
        .onChange(of: scrubbed) { _, value in
            guard let value else { return }
            let clamped = min(max(value, range.lowerBound), range.upperBound)
            if clamped != value { scrubbed = clamped }
        }
        .chartXScale(domain: range, range: .plotDimension(startPadding: 12, endPadding: 12))
        .frame(height: 200)
    }
}
