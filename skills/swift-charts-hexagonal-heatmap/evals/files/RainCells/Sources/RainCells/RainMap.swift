import Charts
import SwiftUI

struct RainCell: Identifiable, Sendable {
    let id: Int
    let longitude: Double
    let latitude: Double
    /// Millimetres of rain over the year, averaged over the gauges in the cell.
    let rainfall: Double
}

struct HexCellShape: ChartSymbolShape {
    var perceptualUnitRect: CGRect {
        CGRect(x: 0.067, y: 0, width: 0.866, height: 1)
    }

    func path(in rect: CGRect) -> Path {
        let quarter = rect.height / 4
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY + quarter))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - quarter))
        path.addLine(to: CGPoint(x: rect.midX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY - quarter))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.minY + quarter))
        path.closeSubpath()
        return path
    }
}

/// Rain gauges across New Zealand, averaged per hexagonal cell.
struct RainMap: View {
    let cells: [RainCell]
    /// Center-to-corner distance of a cell, in degrees.
    let radius: Double

    @State private var plotSize: CGSize = .zero

    var body: some View {
        Chart {
            PointPlot(cells, x: .value("Longitude", \RainCell.longitude), y: .value("Latitude", \RainCell.latitude))
                .foregroundStyle(by: .value("Rainfall", \RainCell.rainfall))
                .symbol(HexCellShape())
                .symbolSize(cellArea)
        }
        .chartForegroundStyleScale(range: Gradient(colors: [.white, .teal, .blue]))
        .chartPlotStyle { plot in
            plot.onGeometryChange(for: CGSize.self) { $0.size } action: { plotSize = $0 }
        }
        .frame(height: 360)
    }

    /// One cell tall, from the plot height and the span of the data.
    private var cellArea: CGFloat {
        let latitudes = cells.map(\.latitude)
        let span = (latitudes.max() ?? 1) - (latitudes.min() ?? 0)
        let cellHeight = plotSize.height / max(span, 0.1) * 2 * radius
        return cellHeight * cellHeight
    }
}
