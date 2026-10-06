import Charts
import SwiftUI

struct Checkin: Identifiable, Sendable {
    let id: UUID
    let longitude: Double
    let latitude: Double
}

struct HexID: Hashable, Sendable {
    let q: Int
    let r: Int
}

struct HexCell: Identifiable, Sendable {
    let id: HexID
    let longitude: Double
    let latitude: Double
    let count: Int
}

struct HexShape: ChartSymbolShape {
    var perceptualUnitRect: CGRect {
        CGRect(x: 0.067, y: 0, width: 0.866, height: 1)
    }

    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.addLines([
            CGPoint(x: rect.midX, y: rect.minY),
            CGPoint(x: rect.maxX, y: rect.minY + rect.height / 4),
            CGPoint(x: rect.maxX, y: rect.maxY - rect.height / 4),
            CGPoint(x: rect.midX, y: rect.maxY),
            CGPoint(x: rect.minX, y: rect.maxY - rect.height / 4),
            CGPoint(x: rect.minX, y: rect.minY + rect.height / 4),
        ])
        path.closeSubpath()
        return path
    }
}

enum Hex {
    static func id(longitude: Double, latitude: Double, radius: Double) -> HexID {
        let q = (sqrt(3) / 3 * longitude - latitude / 3) / radius
        let r = (2.0 / 3 * latitude) / radius
        return HexID(q: Int(q.rounded()), r: Int(r.rounded()))
    }

    static func center(of id: HexID, radius: Double) -> (longitude: Double, latitude: Double) {
        (radius * sqrt(3) * (Double(id.q) + Double(id.r) / 2), radius * 1.5 * Double(id.r))
    }
}

/// Check-ins around a city, counted per hexagon. `checkins` grows while the app runs.
struct CheckinMap: View {
    let checkins: [Checkin]
    let radius = 0.01
    let xDomain = 174.70 ... 174.85
    let yDomain = -41.35 ... -41.22

    @State private var cellSize: CGSize = CGSize(width: 12, height: 14)

    var cells: [HexCell] {
        Dictionary(grouping: checkins) { Hex.id(longitude: $0.longitude, latitude: $0.latitude, radius: radius) }
            .map { id, group in
                let center = Hex.center(of: id, radius: radius)
                return HexCell(id: id, longitude: center.longitude, latitude: center.latitude, count: group.count)
            }
    }

    var body: some View {
        Chart {
            PointPlot(cells, x: .value("Longitude", \HexCell.longitude), y: .value("Latitude", \HexCell.latitude))
                .foregroundStyle(by: .value("Check-ins", \HexCell.count))
                .symbol(HexShape())
                .symbolSize(cellSize)
        }
        .chartXScale(domain: xDomain, range: .plotDimension(padding: 0))
        .chartYScale(domain: yDomain, range: .plotDimension(padding: 0))
        .chartForegroundStyleScale(
            domain: 0 ... (cells.map(\.count).max() ?? 1),
            range: Gradient(colors: [.mint.opacity(0.15), .mint, .indigo])
        )
        .chartLegend(.hidden)
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartPlotStyle { plot in
            plot
                .aspectRatio((xDomain.upperBound - xDomain.lowerBound) / (yDomain.upperBound - yDomain.lowerBound), contentMode: .fit)
                .clipped()
                .onGeometryChange(for: CGSize.self) { $0.size } action: { size in
                    cellSize = CGSize(
                        width: size.width / (xDomain.upperBound - xDomain.lowerBound) * radius * sqrt(3),
                        height: size.height / (yDomain.upperBound - yDomain.lowerBound) * radius * 2
                    )
                }
        }
    }
}
