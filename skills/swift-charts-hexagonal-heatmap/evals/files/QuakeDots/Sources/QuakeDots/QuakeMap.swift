import Charts
import SwiftUI

struct Quake: Identifiable, Sendable {
    let id: Int
    let longitude: Double
    let latitude: Double
    let magnitude: Double
}

enum QuakeCatalogue {
    /// Stand-in for the catalogue download: quakes along a fault line, the same on every run.
    static func sample(count: Int = 50_000) -> [Quake] {
        (0 ..< count).map { index in
            let t = Double(index) / Double(count)
            let wobble = sin(Double(index) * 12.9898) * 0.8
            return Quake(
                id: index,
                longitude: 166.5 + 12 * t + wobble,
                latitude: -46.5 + 11 * t + cos(Double(index) * 78.233) * 0.8,
                magnitude: 2 + abs(sin(Double(index))) * 4
            )
        }
    }
}

/// Every quake as its own dot. With fifty thousand of them the map is one red blob.
struct QuakeMap: View {
    let quakes: [Quake]

    var body: some View {
        Chart {
            PointPlot(quakes, x: .value("Longitude", \Quake.longitude), y: .value("Latitude", \Quake.latitude))
                .foregroundStyle(.red.opacity(0.3))
                .symbolSize(4)
        }
        .chartXScale(domain: 164.0 ... 180.0)
        .chartYScale(domain: -48.5 ... -33.5)
        .frame(height: 420)
    }
}

#Preview {
    QuakeMap(quakes: QuakeCatalogue.sample())
        .padding()
}
