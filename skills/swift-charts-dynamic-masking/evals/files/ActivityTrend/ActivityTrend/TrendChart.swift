import Charts
import SwiftUI

struct WorkoutDay: Identifiable {
    let id = UUID()
    let date: Date
    let minutes: Int
}

/// Weekly workout minutes. Product wants the part after the touched day dimmed,
/// like a stock chart; today the chart only shows the days up to the touch.
struct TrendChart: View {
    let days: [WorkoutDay]
    @State private var touchedDate: Date?

    private var visibleDays: [WorkoutDay] {
        guard let touchedDate else { return days }
        return days.filter { $0.date <= touchedDate }
    }

    var body: some View {
        Chart {
            LinePlot(visibleDays, x: .value("Date", \.date), y: .value("Minutes", \.minutes))
                .interpolationMethod(.catmullRom)
                .symbol(.circle)
            AreaPlot(visibleDays, x: .value("Date", \.date), y: .value("Minutes", \.minutes))
                .interpolationMethod(.catmullRom)
                .opacity(0.25)
        }
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle()
                    .fill(.clear)
                    .contentShape(Rectangle())
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { drag in
                                let origin = geometry[proxy.plotFrame!].origin
                                touchedDate = proxy.value(atX: drag.location.x - origin.x, as: Date.self)
                            }
                            .onEnded { _ in touchedDate = nil }
                    )
            }
        }
        .frame(height: 220)
    }
}
