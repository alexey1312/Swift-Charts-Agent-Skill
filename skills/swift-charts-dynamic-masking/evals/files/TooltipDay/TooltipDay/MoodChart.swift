import Charts
import SwiftUI

struct MoodEntry: Identifiable {
    let id = UUID()
    let date: Date
    let score: Double
}

struct MoodChart: View {
    let entries: [MoodEntry]
    @State private var selection: Date?

    private var nearestEntry: MoodEntry? {
        guard let selection else { return nil }
        return entries.min { abs($0.date.timeIntervalSince(selection)) < abs($1.date.timeIntervalSince(selection)) }
    }

    var body: some View {
        Chart {
            LinePlot(entries, x: .value("Date", \.date), y: .value("Mood", \.score))
            if let selection, let entry = nearestEntry {
                RuleMark(x: .value("Selected", selection))
                    .annotation(position: .top) {
                        VStack {
                            Text(selection, format: .dateTime.weekday(.wide))
                            Text(entry.score, format: .number.precision(.fractionLength(1)))
                        }
                    }
            }
        }
        .chartXSelection(value: $selection)
        .frame(height: 200)
    }
}
