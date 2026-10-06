# Heatmap code

Every Swift block here is complete.
Each one was typechecked against the iOS 27.1 SDK (Xcode 27.1, 27A9269)
at the iOS version its first line names,
and it fails one release below that version.
That is how the availability claims were checked.
`tests/test_samples.py` repeats both checks.
A block marked *continues the block above* is compiled together with that block.
The renders described here come from macOS builds of the same structure
in `scripts/probes/hexagon_probe.swift`.

Use your own model and units.
Keep the structure.

## The grid (iOS 16)

Axial coordinates name each cell with two integers:
`q` counts cells along a row,
and `r` counts rows, each one shifted half a cell to the right.
The grid works in whatever units the chart plots —
degrees, projected map units, or two measures of a scatter plot.

```swift
// typecheck: ios16
import Foundation

/// Axial coordinates of a pointy-top hexagon.
struct HexCoordinate: Hashable, Sendable {
    let q: Int
    let r: Int
}

/// A grid of pointy-top hexagons. `radius` is the distance from a cell's center
/// to a corner, in the units of the chart's x and y values.
struct HexGrid: Sendable {
    let radius: Double

    /// Distance between neighboring centers in a row.
    var columnSpacing: Double { radius * 3.squareRoot() }
    /// Distance between rows.
    var rowSpacing: Double { radius * 1.5 }

    func center(of cell: HexCoordinate) -> (x: Double, y: Double) {
        (x: columnSpacing * (Double(cell.q) + Double(cell.r) / 2),
         y: rowSpacing * Double(cell.r))
    }

    /// The cell whose hexagon contains the point.
    func cell(containingX x: Double, y: Double) -> HexCoordinate {
        let q = (x * 3.squareRoot() / 3 - y / 3) / radius
        let r = (y * 2 / 3) / radius
        return Self.nearest(q: q, r: r)
    }

    /// Rounds q, r and the third cube coordinate s = -q - r, then rebuilds the one
    /// that moved most, so that the three still add up to zero. Rounding q and r on
    /// their own puts about one point in six into a neighboring cell.
    static func nearest(q: Double, r: Double) -> HexCoordinate {
        let s = -q - r
        var roundedQ = q.rounded()
        var roundedR = r.rounded()
        let roundedS = s.rounded()
        let errorQ = abs(roundedQ - q)
        let errorR = abs(roundedR - r)
        let errorS = abs(roundedS - s)
        if errorQ > errorR, errorQ > errorS {
            roundedQ = -roundedR - roundedS
        } else if errorR > errorS {
            roundedR = -roundedQ - roundedS
        }
        return HexCoordinate(q: Int(roundedQ), r: Int(roundedR))
    }
}

/// One occupied cell: its center in plot units and the number of observations in it.
/// The properties are stored, so a vectorized plot reads them without a getter call.
struct HexBin: Identifiable, Sendable {
    let id: HexCoordinate
    let x: Double
    let y: Double
    let count: Int

    var accessibilityLabel: String {
        "Cell at \(x.formatted(.number.precision(.fractionLength(1)))), \(y.formatted(.number.precision(.fractionLength(1))))"
    }

    var accessibilityValue: String {
        "\(count.formatted()) observations"
    }
}

extension HexGrid {
    /// Counts observations per cell. Call it once when the data changes, never from a
    /// view's `body`. Only occupied cells come back, sorted by row and then by column.
    func bins<Observation>(
        _ observations: [Observation],
        x: (Observation) -> Double,
        y: (Observation) -> Double
    ) -> [HexBin] {
        var counts: [HexCoordinate: Int] = [:]
        for observation in observations {
            counts[cell(containingX: x(observation), y: y(observation)), default: 0] += 1
        }
        return counts
            .map { cell, count in
                let center = center(of: cell)
                return HexBin(id: cell, x: center.x, y: center.y, count: count)
            }
            .sorted { ($0.id.r, $0.id.q) < ($1.id.r, $1.id.q) }
    }
}
```

`bins` keeps only a count per cell.
If a cell's accessibility value or a detail view needs more —
the largest magnitude, the latest timestamp —
add that as another stored property while you count.

## The hexagon and its size (iOS 16)

`ChartSymbolShape` requires `perceptualUnitRect`;
a symbol without it does not compile.
`symbolSize(_ size: CGSize)` draws the path in exactly that width and height
(`measured-behavior.md` §1),
so the size comes from each axis's own scale
and the cells tile even when the plot's ratio is a little off (§3).

```swift
// typecheck: ios16, continues the block above
import Charts
import SwiftUI

/// A pointy-top hexagon that fills the rectangle it gets.
struct HexagonSymbol: ChartSymbolShape {
    /// Regular proportions, centered. This matters only when you size the symbol by
    /// area: the hexagon is then as tall as the square root of the area and
    /// 0.866 times as wide. A CGSize gives the width and the height directly.
    var perceptualUnitRect: CGRect {
        let width = 3.squareRoot() / 2
        return CGRect(x: (1 - width) / 2, y: 0, width: width, height: 1)
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

extension HexGrid {
    /// One cell's width and height in points, for a plot of `plotSize` that shows
    /// `xDomain` by `yDomain`. `fill` below 1 leaves a gap between the cells.
    func symbolSize(
        in plotSize: CGSize,
        xDomain: ClosedRange<Double>,
        yDomain: ClosedRange<Double>,
        fill: Double = 1
    ) -> CGSize {
        let pointsPerX = plotSize.width / (xDomain.upperBound - xDomain.lowerBound)
        let pointsPerY = plotSize.height / (yDomain.upperBound - yDomain.lowerBound)
        return CGSize(
            width: columnSpacing * pointsPerX * fill,
            height: 2 * radius * pointsPerY * fill
        )
    }
}

/// Colors for counts. On a symmetric-log scale with slopeAtZero 1, a count lands at
/// log(1 + count) / log(1 + maximum) along the ramp. `.symmetricLog` is iOS 16.4;
/// before it, a linear scale over log(1 + count) puts every count at the same place,
/// but the legend then labels log values.
enum HeatmapColor {
    /// Low counts fade toward the background, so dense cells stand out.
    static let ramp = Gradient(colors: [.blue.opacity(0.12), .blue, .orange, .red])

    static func value(_ count: Int) -> Double {
        if #available(iOS 16.4, *) { return Double(count) }
        return log1p(Double(count))
    }

    static var scaleType: ScaleType {
        if #available(iOS 16.4, *) { return .symmetricLog(slopeAtZero: 1) }
        return .linear
    }
}
```

`fill: 0.96` left 5.8 % of the plot empty between the cells (§2).
A larger `slopeAtZero` gives low counts more of the ramp:
on a domain of 0…10,000, a count of 1 landed at 0.21 with 10 and at 0.07 with 1 (§7).

## The heatmap with marks (iOS 16)

One `PointMark` for each occupied cell.
`PointMark` in `ForEach` drew the same pixels as `PointPlot` (§2),
so this version serves every deployment target;
use the plot version below for many thousands of cells.

```swift
// typecheck: ios16, continues the block above

struct HexHeatmap: View {
    /// From `HexGrid.bins`, computed when the data changed.
    let bins: [HexBin]
    let grid: HexGrid
    let xDomain: ClosedRange<Double>
    let yDomain: ClosedRange<Double>
    private let maximumCount: Int

    /// The plot area's size, read from `chartPlotStyle`.
    @State private var plotSize: CGSize = .zero

    init(bins: [HexBin], grid: HexGrid, xDomain: ClosedRange<Double>, yDomain: ClosedRange<Double>) {
        self.bins = bins
        self.grid = grid
        self.xDomain = xDomain
        self.yDomain = yDomain
        maximumCount = max(1, bins.map(\.count).max() ?? 1)
    }

    var body: some View {
        Chart {
            ForEach(bins) { bin in
                PointMark(x: .value("x", bin.x), y: .value("y", bin.y))
                    .symbol(HexagonSymbol())
                    .symbolSize(cellSize)
                    .foregroundStyle(by: .value("Count", HeatmapColor.value(bin.count)))
                    .accessibilityLabel(bin.accessibilityLabel)
                    .accessibilityValue(bin.accessibilityValue)
            }
        }
        // Explicit domains: an automatic domain includes zero.
        .chartXScale(domain: xDomain, range: .plotDimension(padding: 0))
        .chartYScale(domain: yDomain, range: .plotDimension(padding: 0))
        .chartForegroundStyleScale(
            domain: 0 ... HeatmapColor.value(maximumCount),
            range: HeatmapColor.ramp,
            type: HeatmapColor.scaleType
        )
        .chartPlotStyle { plot in
            plot
                // The plot area, not the whole chart, keeps the domains' ratio.
                .aspectRatio(plotRatio, contentMode: .fit)
                // Cells at the domain's edge stay inside the plot.
                .clipped()
                .onGeometryChange(for: CGSize.self) { $0.size } action: { plotSize = $0 }
        }
    }

    private var cellSize: CGSize {
        grid.symbolSize(in: plotSize, xDomain: xDomain, yDomain: yDomain, fill: 0.96)
    }

    private var plotRatio: CGFloat {
        (xDomain.upperBound - xDomain.lowerBound) / (yDomain.upperBound - yDomain.lowerBound)
    }
}
```

The chart keeps its legend:
a continuous foreground scale draws a color bar with value labels (§8),
and it is the only key to what a color means.
Hide the axes for a map (`.chartXAxis(.hidden)`, `.chartYAxis(.hidden)`);
keep them for a scatter plot of two measures.

## Hexagons in data space (iOS 16)

Each hexagon is three `AreaMark` points — left edge, middle, right edge —
with a band from `yStart` to `yEnd` at each.
The shape is in data units,
so the cells tile at any plot size and any ratio
with no geometry reading at all (§10).
Every cell needs its own `series:`:
without it, cells with the same count joined into one area (§10).

```swift
// typecheck: ios16, continues the block above

/// One edge or the middle of a hexagon, as a vertical band.
struct HexBand: Identifiable, Sendable {
    let id: Int
    let x: Double
    let bottom: Double
    let top: Double
}

extension HexGrid {
    /// The three bands that AreaMark joins into the cell's hexagon.
    func bands(of cell: HexCoordinate, fill: Double = 1) -> [HexBand] {
        let center = center(of: cell)
        let r = radius * fill
        let half = r * 3.squareRoot() / 2
        return [
            HexBand(id: 0, x: center.x - half, bottom: center.y - r / 2, top: center.y + r / 2),
            HexBand(id: 1, x: center.x, bottom: center.y - r, top: center.y + r),
            HexBand(id: 2, x: center.x + half, bottom: center.y - r / 2, top: center.y + r / 2),
        ]
    }
}

struct HexAreaHeatmap: View {
    let bins: [HexBin]
    let grid: HexGrid
    let xDomain: ClosedRange<Double>
    let yDomain: ClosedRange<Double>
    let maximumCount: Int

    var body: some View {
        Chart {
            ForEach(bins) { bin in
                ForEach(grid.bands(of: bin.id, fill: 0.96)) { band in
                    AreaMark(
                        x: .value("x", band.x),
                        yStart: .value("Bottom", band.bottom),
                        yEnd: .value("Top", band.top),
                        series: .value("Cell", "\(bin.id.q),\(bin.id.r)")
                    )
                    .foregroundStyle(by: .value("Count", HeatmapColor.value(bin.count)))
                    .accessibilityLabel(bin.accessibilityLabel)
                    .accessibilityValue(bin.accessibilityValue)
                }
            }
        }
        .chartXScale(domain: xDomain, range: .plotDimension(padding: 0))
        .chartYScale(domain: yDomain, range: .plotDimension(padding: 0))
        .chartForegroundStyleScale(
            domain: 0 ... HeatmapColor.value(max(1, maximumCount)),
            range: HeatmapColor.ramp,
            type: HeatmapColor.scaleType
        )
        .chartPlotStyle { $0.clipped() }
    }
}
```

The price is three marks for each cell.
What VoiceOver reads for them was not measured;
when people must read the map cell by cell,
prefer the symbol version, which is one element for each cell.

## The heatmap with a vectorized plot (iOS 18)

`PointPlot` takes the whole collection and key paths
(WWDC24 10155, 9:43 and 10:21).
An outline — a coastline, a border, a region — is a `LinePlot`
with one `series:` value for each separate segment;
without series, every segment is one line.

```swift
// typecheck: ios18, continues the block above

/// A point on an outline, in the same units as the bins. Each closed ring or
/// separate stretch of the outline has its own `segment`.
struct OutlinePoint: Identifiable, Sendable {
    let id: Int
    let segment: Int
    let x: Double
    let y: Double
}

/// The cells: one hexagon at each occupied cell's center, colored by its count.
struct HexCellsPlot: ChartContent {
    let bins: [HexBin]
    let cellSize: CGSize

    var body: some ChartContent {
        // Key-path modifiers first: `symbol(_:)` and a constant `symbolSize(_:)`
        // return plain chart content, which has no key-path modifiers.
        PointPlot(bins, x: .value("x", \HexBin.x), y: .value("y", \HexBin.y))
            .foregroundStyle(by: .value("Count", \HexBin.count))
            .accessibilityLabel(\HexBin.accessibilityLabel)
            .accessibilityValue(\HexBin.accessibilityValue)
            .symbol(HexagonSymbol())
            .symbolSize(cellSize)
    }
}

/// The outline: one series for each segment, or every segment is one line.
struct OutlinePlot: ChartContent {
    let points: [OutlinePoint]

    var body: some ChartContent {
        LinePlot(points, x: .value("x", \OutlinePoint.x), y: .value("y", \OutlinePoint.y),
                 series: .value("Segment", \OutlinePoint.segment))
            .lineStyle(StrokeStyle(lineWidth: 1, lineJoin: .round))
            .foregroundStyle(.primary)
            .accessibilityHidden(true)
    }
}

struct HexHeatmapPlot: View {
    let bins: [HexBin]
    let outline: [OutlinePoint]
    let grid: HexGrid
    let xDomain: ClosedRange<Double>
    let yDomain: ClosedRange<Double>
    private let maximumCount: Int

    @State private var plotSize: CGSize = .zero

    init(
        bins: [HexBin],
        outline: [OutlinePoint] = [],
        grid: HexGrid,
        xDomain: ClosedRange<Double>,
        yDomain: ClosedRange<Double>
    ) {
        self.bins = bins
        self.outline = outline
        self.grid = grid
        self.xDomain = xDomain
        self.yDomain = yDomain
        maximumCount = max(1, bins.map(\.count).max() ?? 1)
    }

    var body: some View {
        Chart {
            HexCellsPlot(bins: bins, cellSize: cellSize)
            OutlinePlot(points: outline)
        }
        .chartXScale(domain: xDomain, range: .plotDimension(padding: 0))
        .chartYScale(domain: yDomain, range: .plotDimension(padding: 0))
        .chartForegroundStyleScale(
            domain: 0 ... maximumCount,
            range: HeatmapColor.ramp,
            type: .symmetricLog(slopeAtZero: 1)
        )
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartPlotStyle { plot in
            plot
                .aspectRatio(plotRatio, contentMode: .fit)
                .clipped()
                .onGeometryChange(for: CGSize.self) { $0.size } action: { plotSize = $0 }
        }
    }

    private var cellSize: CGSize {
        grid.symbolSize(in: plotSize, xDomain: xDomain, yDomain: yDomain, fill: 0.96)
    }

    private var plotRatio: CGFloat {
        (xDomain.upperBound - xDomain.lowerBound) / (yDomain.upperBound - yDomain.lowerBound)
    }
}
```

The size follows the plot:
`onGeometryChange` inside `chartPlotStyle` reported the new plot size after a resize,
and `ImageRenderer` drew the settled size on its first pass (§11).

## Previews

Synthetic points on a golden-angle spiral are dense at the center and sparse outside,
and they are the same on every run,
so the preview doubles as a fixed state for snapshot tests.

```swift
// typecheck: ios18, continues the block above

#Preview("Spiral density") {
    let grid = HexGrid(radius: 0.4)
    let points: [(x: Double, y: Double)] = (0 ..< 6_000).map { index in
        let distance = (Double(index) / 6_000).squareRoot() * 6
        let angle = Double(index) * 2.399_963
        return (x: distance * cos(angle), y: distance * sin(angle) * 0.75)
    }
    HexHeatmapPlot(
        bins: grid.bins(points, x: \.x, y: \.y),
        grid: grid,
        xDomain: -8 ... 8,
        yDomain: -6 ... 6
    )
    .padding()
}
```

## An equal-area projection (iOS 16)

Longitude and latitude in degrees do not give cells of equal area:
a cell at 34° S covered 24 % more ground than one at 48° S (§9).
Project the points before you bin them —
WWDC24 10155 projects longitude and latitude before it plots them (9:02–9:14) —
and draw the outline in the same projection.

```swift
// typecheck: ios16
import Foundation

/// Lambert's cylindrical equal-area projection with a standard parallel. Every
/// region keeps its ground area, and shapes are true along the standard parallel.
/// Pick the parallel through the middle of the region.
struct EqualAreaProjection: Sendable {
    /// Degrees, negative in the southern hemisphere.
    let standardParallel: Double

    private var scale: Double { cos(standardParallel * .pi / 180) }

    func point(longitude: Double, latitude: Double) -> (x: Double, y: Double) {
        (x: longitude * .pi / 180 * scale,
         y: sin(latitude * .pi / 180) / scale)
    }

    /// A grid radius for cells about `degrees` of latitude from center to corner
    /// near the standard parallel.
    func radius(degrees: Double) -> Double {
        degrees * .pi / 180
    }
}
```

With the standard parallel at 41° S,
every cell from 34° S to 48° S covered 2,890 km²,
and a cell's east–west stretch stayed between ×0.91 and ×1.13 (§9).
Compute the domains from the projected corners of the region,
so that the plot ratio stays correct.
