import Charts
import SwiftUI

struct QuakeCell: Identifiable, Sendable {
    let id: Int
    let longitude: Double
    let latitude: Double
    let count: Int
}

struct Hexagon: ChartSymbolShape {
    var perceptualUnitRect: CGRect {
        CGRect(x: 0.067, y: 0, width: 0.866, height: 1)
    }

    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.addLines([
            CGPoint(x: rect.midX, y: rect.minY),
            CGPoint(x: rect.maxX, y: rect.minY + rect.height * 0.25),
            CGPoint(x: rect.maxX, y: rect.minY + rect.height * 0.75),
            CGPoint(x: rect.midX, y: rect.maxY),
            CGPoint(x: rect.minX, y: rect.minY + rect.height * 0.75),
            CGPoint(x: rect.minX, y: rect.minY + rect.height * 0.25),
        ])
        path.closeSubpath()
        return path
    }
}

/// Earthquake counts per hexagonal cell. The cells are binned elsewhere, once.
struct QuakeHexMap: View {
    let cells: [QuakeCell]
    /// Center-to-corner distance of a cell, in degrees.
    let radius: Double
    let xDomain = 164.0 ... 180.0
    let yDomain = -48.5 ... -33.5

    @State private var plotWidth: CGFloat = 0

    var body: some View {
        Chart {
            PointPlot(cells, x: .value("Longitude", \QuakeCell.longitude), y: .value("Latitude", \QuakeCell.latitude))
                .foregroundStyle(by: .value("Quakes", \QuakeCell.count))
                .symbol(Hexagon())
                .symbolSize(symbolArea)
        }
        .chartXScale(domain: xDomain, range: .plotDimension(padding: 0))
        .chartYScale(domain: yDomain, range: .plotDimension(padding: 0))
        .chartForegroundStyleScale(
            domain: 0 ... maximumCount,
            range: Gradient(colors: [.yellow.opacity(0.2), .orange, .red]),
            type: .symmetricLog(slopeAtZero: 1)
        )
        .chartPlotStyle { plot in
            plot
                .clipped()
                .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { plotWidth = $0 }
        }
        .frame(height: 300)
    }

    /// Screen points per degree, times the cell's width, squared; 0.92 leaves a small gap.
    private var symbolArea: CGFloat {
        let cellWidth = plotWidth / (xDomain.upperBound - xDomain.lowerBound) * radius * sqrt(3)
        return max(18, cellWidth * cellWidth * 0.92)
    }

    private var maximumCount: Int {
        max(1, cells.map(\.count).max() ?? 1)
    }
}
