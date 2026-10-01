import Charts
import SwiftUI

struct BalancePoint: Identifiable {
    let id = UUID()
    let date: Date
    let amount: Double
    let isForecast: Bool
}

/// Account balance: recorded days, then a model's forecast.
/// Design wants one line, solid up to today and dashed after it.
struct BalanceChart: View {
    let points: [BalancePoint]

    var body: some View {
        Chart {
            LinePlot(points.filter { !$0.isForecast }, x: .value("Date", \.date), y: .value("Balance", \.amount))
                .interpolationMethod(.catmullRom)
            LinePlot(points.filter { $0.isForecast }, x: .value("Date", \.date), y: .value("Balance", \.amount))
                .interpolationMethod(.catmullRom)
                .lineStyle(StrokeStyle(lineWidth: 2, dash: [4, 4]))
        }
        .frame(height: 200)
    }
}
