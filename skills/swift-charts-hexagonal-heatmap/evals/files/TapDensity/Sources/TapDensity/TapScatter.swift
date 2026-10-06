import Charts
import SwiftUI

/// Where a person tapped on the home screen, in points from its top-left corner.
struct Tap: Identifiable, Sendable {
    let id: Int
    let x: Double
    let y: Double
}

/// Every tap as a dot over a 390 × 844 pt screen. Busy places turn into solid ink.
struct TapScatter: View {
    let taps: [Tap]

    var body: some View {
        Chart {
            ForEach(taps) { tap in
                PointMark(x: .value("x", tap.x), y: .value("y", tap.y))
                    .symbolSize(10)
                    .foregroundStyle(.purple.opacity(0.25))
            }
        }
        .chartXScale(domain: 0.0 ... 390.0)
        .chartYScale(domain: 0.0 ... 844.0, range: .plotDimension(startPadding: 0, endPadding: 0))
        .chartYAxis {
            AxisMarks(position: .leading)
        }
        .aspectRatio(390.0 / 844.0, contentMode: .fit)
    }
}
