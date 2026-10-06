// Re-derives every "Measured" statement in the swift-charts-hexagonal-heatmap skill.
//
//   xcrun swiftc -O -suppress-warnings scripts/probes/hexagon_probe.swift -o "$TMPDIR/hexagon_probe"
//   "$TMPDIR/hexagon_probe" [--png <directory>]
//
// It renders small charts on macOS with ImageRenderer and measures their pixels, hosts
// some in an offscreen window to read what ChartProxy reports, and runs the binning
// and map-projection arithmetic the skill recommends. The tiling charts have no axes
// and fixed scales, so every cell's pixel position is known. Swift Charts is the same
// framework on iOS and macOS; these are measurements of its layout and drawing.

import AppKit
import Charts
import SwiftUI

// MARK: - Hexagons

/// Pointy-top hexagon spread over the whole rectangle it is given:
/// the top and bottom corners at the horizontal middle, the others a quarter of the height in.
func hexagonPath(in rect: CGRect) -> Path {
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

let regularWidth = sqrt(3.0) / 2  // a regular pointy-top hexagon's width over its height

struct Hexagon: ChartSymbolShape {
    var unit = CGRect(x: 0, y: 0, width: 1, height: 1)
    var perceptualUnitRect: CGRect { unit }
    func path(in rect: CGRect) -> Path { hexagonPath(in: rect) }
}

/// The perceptual rectangle the article settles on: regular proportions, centered.
let narrowUnit = CGRect(x: (1 - regularWidth) / 2, y: 0, width: regularWidth, height: 1)

struct Square: ChartSymbolShape {
    var perceptualUnitRect: CGRect { CGRect(x: 0, y: 0, width: 1, height: 1) }
    func path(in rect: CGRect) -> Path { Path(rect) }
}

// MARK: - Pixels

struct Bitmap {
    let width: Int, height: Int
    private let pixels: [UInt8]

    init(_ image: CGImage) {
        width = image.width
        height = image.height
        var buffer = [UInt8](repeating: 0, count: width * height * 4)
        let context = CGContext(
            data: &buffer, width: width, height: height, bitsPerComponent: 8, bytesPerRow: width * 4,
            space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )!
        context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
        pixels = buffer
    }

    /// Top-left origin, like SwiftUI. Components 0…1.
    func rgb(_ x: Int, _ y: Int) -> (Double, Double, Double) {
        let index = (y * width + x) * 4
        return (Double(pixels[index]) / 255, Double(pixels[index + 1]) / 255, Double(pixels[index + 2]) / 255)
    }

    func gray(_ x: Int, _ y: Int) -> Double {
        let (r, g, b) = rgb(x, y)
        return (r + g + b) / 3
    }

    /// Bounding box of the pixels darker than mid-gray.
    func inkBox() -> CGRect? {
        var minX = width, minY = height, maxX = -1, maxY = -1
        for y in 0 ..< height { for x in 0 ..< width where gray(x, y) < 0.5 {
            minX = min(minX, x); maxX = max(maxX, x); minY = min(minY, y); maxY = max(maxY, y)
        } }
        return maxX < 0 ? nil : CGRect(x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1)
    }

    /// Strongly red pixels inside `columns`.
    func redPixels(columns: Range<Int>) -> Int {
        var count = 0
        for y in 0 ..< height { for x in columns where x >= 0 && x < width {
            let (r, g, b) = rgb(x, y)
            if r > 0.6 && g < 0.4 && b < 0.4 { count += 1 }
        } }
        return count
    }
}

@MainActor var pngDirectory: URL?

@MainActor func render(_ name: String, _ view: some View, scale: CGFloat = 1) -> Bitmap {
    let renderer = ImageRenderer(content: view)
    renderer.scale = scale
    let image = renderer.cgImage!
    if let pngDirectory {
        let data = NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:])!
        try? data.write(to: pngDirectory.appendingPathComponent("\(name).png"))
    }
    return Bitmap(image)
}

@MainActor func host(_ view: some View, size: CGSize) {
    let window = NSWindow(contentRect: NSRect(origin: .zero, size: size), styleMask: [.borderless], backing: .buffered, defer: false)
    window.contentView = NSHostingView(rootView: view)
    window.contentView?.layoutSubtreeIfNeeded()
    RunLoop.main.run(until: Date().addingTimeInterval(0.4))
    window.close()
}

/// Reads the plot frame once the chart is laid out.
struct PlotFrameReader: View {
    let proxy: ChartProxy
    let report: (CGRect) -> Void
    var body: some View {
        GeometryReader { geometry in
            Color.clear.onAppear { if let frame = proxy.plotFrame { report(geometry[frame]) } }
        }
    }
}

func format(_ value: Double, _ digits: Int = 1) -> String { String(format: "%.\(digits)f", value) }

// MARK: - §1 The symbol's drawing box

enum Sizing {
    case area(CGFloat)
    case box(CGSize)
    /// `symbolSize(by: .value(_, 1))` and a size scale whose range ends at the area.
    case scaledArea(CGFloat)
}

struct OneSymbol<S: ChartSymbolShape>: View {
    let shape: S
    let sizing: Sizing

    @ChartContentBuilder var point: some ChartContent {
        let mark = PointMark(x: .value("x", 0.0), y: .value("y", 0.0)).symbol(shape).foregroundStyle(.black)
        switch sizing {
        case let .area(area): mark.symbolSize(area)
        case let .box(size): mark.symbolSize(size)
        case .scaledArea: mark.symbolSize(by: .value("Cell", 1))
        }
    }

    var body: some View {
        sized(
            Chart { point }
                .chartXScale(domain: -1.0 ... 1.0, range: .plotDimension(padding: 0))
                .chartYScale(domain: -1.0 ... 1.0, range: .plotDimension(padding: 0))
                .chartXAxis(.hidden)
                .chartYAxis(.hidden)
                .chartLegend(.hidden)
        )
        .frame(width: 200, height: 200)
        .background(Color.white)
    }

    @ViewBuilder func sized(_ chart: some View) -> some View {
        if case let .scaledArea(area) = sizing {
            chart.chartSymbolSizeScale(domain: 0 ... 1, range: 0 ... area)
        } else {
            chart
        }
    }
}

/// Measured at 4× and reported in points.
@MainActor func box(_ name: String, _ view: some View) -> CGSize {
    let ink = render(name, view, scale: 4).inkBox()!
    return CGSize(width: ink.width / 4, height: ink.height / 4)
}

@MainActor func symbolReport() -> (heightPerRootArea: Double, widthPerRootArea: Double) {
    print("1. The symbol's drawing box (one PointMark, rendered at 4×, ink measured in pt)")
    let area: CGFloat = 1600
    let rows: [(String, CGSize)] = [
        ("square path, perceptualUnitRect 0,0,1,1, symbolSize(1600)", box("1-square", OneSymbol(shape: Square(), sizing: .area(area)))),
        (".circle, symbolSize(1600)", box("1-circle", OneSymbol(shape: .circle, sizing: .area(area)))),
        ("hexagon path, perceptualUnitRect 0,0,1,1, symbolSize(1600)", box("1-hexagon-unit", OneSymbol(shape: Hexagon(), sizing: .area(area)))),
        ("hexagon path, perceptualUnitRect 0.067,0,0.866,1, symbolSize(1600)", box("1-hexagon-narrow", OneSymbol(shape: Hexagon(unit: narrowUnit), sizing: .area(area)))),
        ("the same, symbolSize(400)", box("1-hexagon-narrow-400", OneSymbol(shape: Hexagon(unit: narrowUnit), sizing: .area(400)))),
        ("the same, size scale 0…1 → 0…1600, value 1", box("1-hexagon-scaled", OneSymbol(shape: Hexagon(unit: narrowUnit), sizing: .scaledArea(area)))),
        ("hexagon path, perceptualUnitRect 0,0,1,1, symbolSize(CGSize(34.64, 40))", box("1-hexagon-box", OneSymbol(shape: Hexagon(), sizing: .box(CGSize(width: 34.64, height: 40))))),
        ("hexagon path, perceptualUnitRect 0.067,0,0.866,1, symbolSize(CGSize(34.64, 40))", box("1-hexagon-narrow-box", OneSymbol(shape: Hexagon(unit: narrowUnit), sizing: .box(CGSize(width: 34.64, height: 40))))),
    ]
    for (label, size) in rows {
        print("   \(label.padding(toLength: 80, withPad: " ", startingAt: 0)) \(format(size.width)) × \(format(size.height)) pt (w/h \(format(size.width / size.height, 3)))")
    }
    let narrow = rows[3].1
    return (Double(narrow.height) / sqrt(Double(area)), Double(narrow.width) / sqrt(Double(area)))
}

// MARK: - §2–3 Tiling

struct Cell: Identifiable {
    let q: Int, r: Int
    var id: String { "\(q),\(r)" }
    var x: Double { radius * sqrt(3) * (Double(q) + Double(r) / 2) }
    var y: Double { radius * 1.5 * Double(r) }
}

let radius = 1.0
let tileX = -8.0 ... 8.0, tileY = -6.0 ... 6.0  // 4:3
let tileCells: [Cell] = (-8 ... 8).flatMap { r in (-12 ... 12).map { Cell(q: $0, r: r) } }
    .filter { tileX.contains($0.x) && tileY.contains($0.y) }

enum TileShape { case unit, narrow }

struct TileChart: View {
    let shape: TileShape
    let sizing: Sizing
    var size = CGSize(width: 480, height: 360)
    var vectorized = true

    @ChartContentBuilder var cells: some ChartContent {
        if vectorized {
            switch (shape, sizing) {
            case let (.unit, .box(box)): PointPlot(tileCells, x: .value("x", \.x), y: .value("y", \.y)).symbol(Hexagon()).symbolSize(box).foregroundStyle(.black.opacity(0.5))
            case let (.narrow, .area(area)): PointPlot(tileCells, x: .value("x", \.x), y: .value("y", \.y)).symbol(Hexagon(unit: narrowUnit)).symbolSize(area).foregroundStyle(.black.opacity(0.5))
            default: PointPlot(tileCells, x: .value("x", \.x), y: .value("y", \.y))
            }
        } else {
            ForEach(tileCells) { cell in
                switch (shape, sizing) {
                case let (.unit, .box(box)): PointMark(x: .value("x", cell.x), y: .value("y", cell.y)).symbol(Hexagon()).symbolSize(box).foregroundStyle(.black.opacity(0.5))
                case let (.narrow, .area(area)): PointMark(x: .value("x", cell.x), y: .value("y", cell.y)).symbol(Hexagon(unit: narrowUnit)).symbolSize(area).foregroundStyle(.black.opacity(0.5))
                default: PointMark(x: .value("x", cell.x), y: .value("y", cell.y))
                }
            }
        }
    }

    var body: some View {
        Chart { cells }
            .chartXScale(domain: tileX, range: .plotDimension(padding: 0))
            .chartYScale(domain: tileY, range: .plotDimension(padding: 0))
            .chartXAxis(.hidden)
            .chartYAxis(.hidden)
            .frame(width: size.width, height: size.height)
            .background(Color.white)
    }
}

/// Black at 50 % over white: one layer is mid-gray, two are dark, none is white.
/// Counted inside x −4…4, y −3…3, away from the grid's ragged border.
func coverage(_ bitmap: Bitmap, size: CGSize, origin: CGPoint = .zero) -> (gap: Double, overlap: Double) {
    let kx = size.width / (tileX.upperBound - tileX.lowerBound)
    let ky = size.height / (tileY.upperBound - tileY.lowerBound)
    let columns = Int(origin.x + (-4 - tileX.lowerBound) * kx) ..< Int(origin.x + (4 - tileX.lowerBound) * kx)
    let rows = Int(origin.y + (tileY.upperBound - 3) * ky) ..< Int(origin.y + (tileY.upperBound + 3) * ky)
    var gap = 0, overlap = 0, total = 0
    for y in rows { for x in columns {
        let value = bitmap.gray(x, y)
        total += 1
        if value > 0.9 { gap += 1 } else if value < 0.375 { overlap += 1 }
    } }
    return (100 * Double(gap) / Double(total), 100 * Double(overlap) / Double(total))
}

func percent(_ value: (gap: Double, overlap: Double)) -> String {
    "gap \(format(value.gap))%, overlap \(format(value.overlap))%"
}

@MainActor func tilingReport(heightPerRootArea: Double) {
    print("\n2. Tiling: \(tileCells.count) cells, radius 1, domain 16 × 12, plot 480 × 360 pt (30 pt per unit both ways)")
    let size = CGSize(width: 480, height: 360)
    let k = 30.0
    let cellWidth = sqrt(3) * radius * k, cellHeight = 2 * radius * k
    let article = cellWidth * cellWidth * 0.92
    // The area whose narrow hexagon is exactly one cell tall, from §1's measured proportion.
    let exact = pow(cellHeight / heightPerRootArea, 2)
    let rows: [(String, TileChart)] = [
        ("narrow rect, area = (cell width)² × 0.92 = \(Int(article))", TileChart(shape: .narrow, sizing: .area(article))),
        ("narrow rect, area = (cell height)² = \(Int(exact.rounded()))", TileChart(shape: .narrow, sizing: .area(exact))),
        ("unit rect, symbolSize(CGSize(cell width, cell height))", TileChart(shape: .unit, sizing: .box(CGSize(width: cellWidth, height: cellHeight)))),
        ("the same, ForEach + PointMark", TileChart(shape: .unit, sizing: .box(CGSize(width: cellWidth, height: cellHeight)), vectorized: false)),
        ("unit rect, CGSize × 0.96 each way", TileChart(shape: .unit, sizing: .box(CGSize(width: cellWidth * 0.96, height: cellHeight * 0.96)))),
    ]
    var renders: [Bitmap] = []
    for (index, (label, chart)) in rows.enumerated() {
        let bitmap = render("2-\(index)", chart)
        renders.append(bitmap)
        print("   \(label.padding(toLength: 62, withPad: " ", startingAt: 0)) \(percent(coverage(bitmap, size: size)))")
    }
    var differing = 0
    for y in 0 ..< renders[2].height { for x in 0 ..< renders[2].width where abs(renders[2].gray(x, y) - renders[3].gray(x, y)) > 0.02 { differing += 1 } }
    print("   PointPlot against ForEach + PointMark: \(differing) px differ")

    print("\n3. Plot proportions (domain 16 × 12, so 4:3)")
    let aspect = 16.0 / 12.0
    var frames: [String: CGRect] = [:]
    func reader(_ key: String) -> (ChartProxy) -> PlotFrameReader {
        { proxy in PlotFrameReader(proxy: proxy) { frames[key] = $0 } }
    }
    let base = { (key: String) in
        Chart { PointPlot(tileCells, x: .value("x", \.x), y: .value("y", \.y)) }
            .chartXScale(domain: tileX, range: .plotDimension(padding: 0))
            .chartYScale(domain: tileY, range: .plotDimension(padding: 0))
            .chartOverlay { reader(key)($0) }
    }
    let variants: [(String, AnyView)] = [
        ("axes hidden, .aspectRatio(4/3) on the chart", AnyView(base("hidden").chartXAxis(.hidden).chartYAxis(.hidden).aspectRatio(aspect, contentMode: .fit))),
        ("axes shown, .aspectRatio(4/3) on the chart", AnyView(base("shown").aspectRatio(aspect, contentMode: .fit))),
        ("axes shown, .chartPlotStyle { $0.aspectRatio(4/3) }", AnyView(base("plotStyle").chartPlotStyle { $0.aspectRatio(aspect, contentMode: .fit) })),
    ]
    let keys = ["hidden", "shown", "plotStyle"]
    for (index, (label, view)) in variants.enumerated() {
        host(view.frame(width: 480, height: 480), size: CGSize(width: 480, height: 480))
        guard let frame = frames[keys[index]] else { print("   \(label): no plot frame reported"); continue }
        let kx = frame.width / 16, ky = frame.height / 12
        print("   \(label.padding(toLength: 56, withPad: " ", startingAt: 0)) plot \(format(frame.width)) × \(format(frame.height)) pt, ratio \(format(frame.width / frame.height, 3)), y/x scale \(format(100 * (ky / kx - 1), 1))%")
    }

    for zeroPadding in [false, true] {
        var edges = (lower: CGFloat.nan, upper: CGFloat.nan, width: CGFloat.nan)
        host(RangeChart(zeroPadding: zeroPadding) { edges = ($0, $1, $2) }, size: CGSize(width: 480, height: 360))
        let label = zeroPadding ? "chartXScale(domain:range: .plotDimension(padding: 0))" : "chartXScale(domain:) with no range"
        print("   \(label.padding(toLength: 56, withPad: " ", startingAt: 0)) x −8 at \(format(edges.lower)) pt, x 8 at \(format(edges.upper)) pt, plot \(format(edges.width)) pt wide")
    }

    let squat = CGSize(width: 480, height: 300)  // 30 pt per unit across, 25 down
    let squatWidth = sqrt(3) * radius * 30, squatHeight = 2 * radius * 25
    // One cell tall by the x scale, the way a size taken from the plot width comes out.
    let squatArea = pow(2 * radius * 30, 2)
    print("   plot 480 × 300 instead (x 30 pt per unit, y 25):")
    print("     narrow rect, area = (cell height by the x scale)²:".padding(toLength: 64, withPad: " ", startingAt: 0),
          percent(coverage(render("3-squat-area", TileChart(shape: .narrow, sizing: .area(squatArea), size: squat)), size: squat)))
    print("     unit rect, symbolSize(CGSize(30·√3, 25·2)):".padding(toLength: 64, withPad: " ", startingAt: 0),
          percent(coverage(render("3-squat-box", TileChart(shape: .unit, sizing: .box(CGSize(width: squatWidth, height: squatHeight)), size: squat)), size: squat)))
}

/// Where the domain's ends land in a plot with hexagon symbols, with and without range padding.
struct RangeChart: View {
    let zeroPadding: Bool
    let report: (CGFloat, CGFloat, CGFloat) -> Void

    var body: some View {
        ranged(
            Chart {
                PointPlot(tileCells, x: .value("x", \.x), y: .value("y", \.y))
                    .symbol(Hexagon(unit: narrowUnit))
                    .symbolSize(3600)
            }
            .chartXAxis(.hidden)
            .chartYAxis(.hidden)
            .chartOverlay { proxy in
                GeometryReader { geometry in
                    Color.clear.onAppear {
                        guard let frame = proxy.plotFrame else { return }
                        report(proxy.position(forX: tileX.lowerBound) ?? .nan, proxy.position(forX: tileX.upperBound) ?? .nan, geometry[frame].width)
                    }
                }
            }
        )
        .frame(width: 480, height: 360)
    }

    @ViewBuilder func ranged(_ chart: some View) -> some View {
        if zeroPadding {
            chart.chartXScale(domain: tileX, range: .plotDimension(padding: 0)).chartYScale(domain: tileY, range: .plotDimension(padding: 0))
        } else {
            chart.chartXScale(domain: tileX).chartYScale(domain: tileY)
        }
    }
}

// MARK: - §4 Automatic domains

struct Place: Identifiable {
    let id: Int
    let longitude: Double, latitude: Double
}

let places = [Place(id: 0, longitude: 166.4, latitude: -47.2), Place(id: 1, longitude: 178.6, latitude: -34.1), Place(id: 2, longitude: 172.6, latitude: -41.3)]

@MainActor func domainReport() {
    print("\n4. Automatic domains (points at longitude 166.4…178.6, latitude −47.2…−34.1, no chartXScale or chartYScale)")
    var x: [Double] = [], y: [Double] = []
    let chart = Chart { PointPlot(places, x: .value("Longitude", \.longitude), y: .value("Latitude", \.latitude)) }
        .chartOverlay { proxy in
            Color.clear.onAppear {
                x = proxy.xDomain(dataType: Double.self)
                y = proxy.yDomain(dataType: Double.self)
            }
        }
        .frame(width: 400, height: 400)
    host(chart, size: CGSize(width: 400, height: 400))
    print("   x domain: \(x.map { format($0) }.joined(separator: " … "))")
    print("   y domain: \(y.map { format($0) }.joined(separator: " … "))")
}

// MARK: - §5 Cells outside an explicit domain

struct EdgeChart: View {
    let clipped: Bool
    var onFrame: ((CGRect) -> Void)? = nil
    let points = [Place(id: 0, longitude: 10.6, latitude: 5), Place(id: 1, longitude: 9.8, latitude: 2)]

    var body: some View {
        styled(
            Chart {
                PointPlot(points, x: .value("x", \.longitude), y: .value("y", \.latitude))
                    .symbol(Hexagon(unit: narrowUnit))
                    .symbolSize(900)
                    .foregroundStyle(.red)
            }
            .chartXScale(domain: 0.0 ... 10.0, range: .plotDimension(padding: 0))
            .chartYScale(domain: 0.0 ... 10.0, range: .plotDimension(padding: 0))
            .chartOverlay { proxy in PlotFrameReader(proxy: proxy) { onFrame?($0) } }
        )
        .frame(width: 400, height: 300)
        .background(Color.white)
    }

    @ViewBuilder func styled(_ chart: some View) -> some View {
        if clipped { chart.chartPlotStyle { $0.clipped() } } else { chart }
    }
}

@MainActor func edgeReport() {
    print("\n5. Cells past an explicit domain (x 0…10; red hexagons centered at x 10.6 and 9.8, axes shown)")
    var plot = CGRect.zero
    host(EdgeChart(clipped: false) { plot = $0 }, size: CGSize(width: 400, height: 300))
    for clipped in [false, true] {
        let bitmap = render("5-\(clipped ? "clipped" : "default")", EdgeChart(clipped: clipped))
        let outside = bitmap.redPixels(columns: Int(plot.maxX.rounded(.up)) ..< bitmap.width)
        let inside = bitmap.redPixels(columns: 0 ..< Int(plot.maxX.rounded(.down)))
        print("   \((clipped ? ".chartPlotStyle { $0.clipped() }:" : "default:").padding(toLength: 36, withPad: " ", startingAt: 0)) \(outside) red px right of the plot, \(inside) inside it")
    }
}

// MARK: - §6 Binning

struct SplitMix64: RandomNumberGenerator {
    var state: UInt64
    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }
}

func fractional(x: Double, y: Double, radius: Double) -> (q: Double, r: Double) {
    ((sqrt(3) / 3 * x - y / 3) / radius, (2.0 / 3 * y) / radius)
}

func center(q: Int, r: Int, radius: Double) -> (x: Double, y: Double) {
    (radius * sqrt(3) * (Double(q) + Double(r) / 2), radius * 1.5 * Double(r))
}

/// Round all three cube coordinates, then rebuild the one that moved most.
func cubeRounded(q: Double, r: Double) -> (Int, Int) {
    let s = -q - r
    var rq = q.rounded(), rr = r.rounded()
    let rs = s.rounded()
    let dq = abs(rq - q), dr = abs(rr - r), ds = abs(rs - s)
    if dq > dr && dq > ds { rq = -rr - rs } else if dr > ds { rr = -rq - rs }
    return (Int(rq), Int(rr))
}

func nearest(x: Double, y: Double, radius: Double) -> (Int, Int) {
    let guess = fractional(x: x, y: y, radius: radius)
    var best = (0, 0), bestDistance = Double.infinity
    for q in Int(guess.q.rounded()) - 2 ... Int(guess.q.rounded()) + 2 {
        for r in Int(guess.r.rounded()) - 2 ... Int(guess.r.rounded()) + 2 {
            let c = center(q: q, r: r, radius: radius)
            let distance = (c.x - x) * (c.x - x) + (c.y - y) * (c.y - y)
            if distance < bestDistance { bestDistance = distance; best = (q, r) }
        }
    }
    return best
}

func binningReport() {
    print("\n6. Binning 1,000,000 uniform random points (seeded), radius 0.3, against the nearest cell center")
    var generator = SplitMix64(state: 2026)
    var independentWrong = 0, cubeWrong = 0
    let count = 1_000_000
    for _ in 0 ..< count {
        let x = Double.random(in: 164 ... 180, using: &generator)
        let y = Double.random(in: -48.5 ... -33.5, using: &generator)
        let truth = nearest(x: x, y: y, radius: 0.3)
        let f = fractional(x: x, y: y, radius: 0.3)
        if (Int(f.q.rounded()), Int(f.r.rounded())) != truth { independentWrong += 1 }
        if cubeRounded(q: f.q, r: f.r) != truth { cubeWrong += 1 }
    }
    print("   q and r rounded independently: \(format(100 * Double(independentWrong) / Double(count), 2))% in the wrong cell")
    print("   cube rounding (s = −q − r):    \(format(100 * Double(cubeWrong) / Double(count), 2))% in the wrong cell")
}

// MARK: - §7 Color scale

struct Count: Identifiable {
    let id: Int
    let value: Int
}

struct ColorChart: View {
    let counts: [Double]
    let type: ScaleType
    let maximum: Double

    var body: some View {
        Chart {
            ForEach(counts.indices, id: \.self) { index in
                PointMark(x: .value("Index", Double(index)), y: .value("y", 0.0))
                    .symbol(Square())
                    .symbolSize(400)
                    .foregroundStyle(by: .value("Count", counts[index]))
            }
        }
        .chartForegroundStyleScale(domain: 0.0 ... maximum, range: Gradient(colors: [.black, .white]), type: type)
        .chartXScale(domain: -0.5 ... Double(counts.count) - 0.5, range: .plotDimension(padding: 0))
        .chartYScale(domain: -1.0 ... 1.0, range: .plotDimension(padding: 0))
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartLegend(.hidden)
        .frame(width: CGFloat(counts.count) * 40, height: 40)
        .background(Color.red)
    }
}

@MainActor func grays(_ name: String, _ chart: ColorChart) -> [Double] {
    let bitmap = render(name, chart)
    return chart.counts.indices.map { bitmap.gray($0 * 40 + 20, 20) }
}

@MainActor func colorReport() {
    print("\n7. Where counts land on a black→white gradient, domain 0…10,000 (0 = start, 1 = end)")
    let maximum = 10_000.0
    // Calibrate gray against position with the linear scale, which maps t = count / maximum.
    let steps = (0 ... 20).map { Double($0) * maximum / 20 }
    let table = grays("7-calibration", ColorChart(counts: steps, type: .linear, maximum: maximum))
    func position(_ gray: Double) -> Double {
        for index in 1 ..< table.count where gray <= table[index] {
            let low = table[index - 1], high = table[index]
            let fraction = high > low ? (gray - low) / (high - low) : 0
            return (Double(index - 1) + fraction) / 20
        }
        return 1
    }
    let counts: [Double] = [1, 10, 100, 1000, 10_000]
    print("   count:".padding(toLength: 50, withPad: " ", startingAt: 0), counts.map { String(Int($0)).padding(toLength: 7, withPad: " ", startingAt: 0) }.joined())
    let scales: [(String, ScaleType, Double?)] = [
        (".linear", .linear, nil),
        (".symmetricLog", .symmetricLog, nil),
        (".symmetricLog(slopeAtZero: 1)", .symmetricLog(slopeAtZero: 1), 1),
        (".symmetricLog(slopeAtZero: 0.1)", .symmetricLog(slopeAtZero: 0.1), 0.1),
        (".symmetricLog(slopeAtZero: 10)", .symmetricLog(slopeAtZero: 10), 10),
    ]
    var fits: [String] = []
    for (index, (label, type, slope)) in scales.enumerated() {
        let measured = grays("7-\(index)", ColorChart(counts: counts, type: type, maximum: maximum)).map(position)
        print("   \(label.padding(toLength: 47, withPad: " ", startingAt: 0)) \(measured.map { format($0, 3).padding(toLength: 7, withPad: " ", startingAt: 0) }.joined())")
        if let slope {
            // Candidate: t = log(1 + count × slope) / log(1 + maximum × slope).
            let predicted = counts.map { log1p($0 * slope) / log1p(maximum * slope) }
            let error = zip(measured, predicted).map { abs($0 - $1) }.max()!
            fits.append("slopeAtZero \(format(slope, 1)): largest gap \(format(error, 3))")
        }
    }
    let logged = grays("7-log1p", ColorChart(counts: counts.map { log1p($0) }, type: .linear, maximum: log1p(maximum))).map(position)
    print("   \(".linear over log1p(count), domain 0…log1p(max)".padding(toLength: 47, withPad: " ", startingAt: 0)) \(logged.map { format($0, 3).padding(toLength: 7, withPad: " ", startingAt: 0) }.joined())")
    print("   t = log(1 + count × slopeAtZero) / log(1 + max × slopeAtZero) against the rows above:\n     \(fits.joined(separator: "; "))")
}

// MARK: - §8 Legend

struct LegendChart: View {
    let hidden: Bool
    var onFrame: ((CGRect) -> Void)? = nil
    let counts = [Count(id: 0, value: 1), Count(id: 1, value: 50), Count(id: 2, value: 100)]

    var body: some View {
        legend(
            Chart {
                PointPlot(counts, x: .value("Index", \.id), y: .value("y", \.value))
                    .foregroundStyle(by: .value("Count", \.value))
            }
            .chartForegroundStyleScale(domain: 0 ... 100, range: Gradient(colors: [.blue, .red]), type: .linear)
            .chartXAxis(.hidden)
            .chartYAxis(.hidden)
            .chartOverlay { proxy in PlotFrameReader(proxy: proxy) { onFrame?($0) } }
        )
        .frame(width: 400, height: 300)
        .background(Color.white)
    }

    @ViewBuilder func legend(_ chart: some View) -> some View {
        if hidden { chart.chartLegend(.hidden) } else { chart }
    }
}

@MainActor func legendReport() {
    print("\n8. Legend of a continuous foregroundStyle(by:) scale (chart 400 × 300, axes hidden)")
    var shown = CGRect.zero, hidden = CGRect.zero
    host(LegendChart(hidden: false) { shown = $0 }, size: CGSize(width: 400, height: 300))
    host(LegendChart(hidden: true) { hidden = $0 }, size: CGSize(width: 400, height: 300))
    let bitmap = render("8-legend", LegendChart(hidden: false))
    // Saturated pixels below the plot are the legend's color bar; tick labels are gray.
    var bar = 0, columns = Set<Int>()
    for y in Int(shown.maxY) + 1 ..< bitmap.height { for x in 0 ..< bitmap.width {
        let (r, g, b) = bitmap.rgb(x, y)
        if max(r, g, b) - min(r, g, b) > 0.3 { bar += 1; columns.insert(x) }
    } }
    let width = (columns.max() ?? 0) - (columns.min() ?? 0) + 1
    print("   default:              plot height \(format(shown.height)) pt; a color bar below it, \(bar) px, \(columns.isEmpty ? 0 : width) pt wide")
    print("   .chartLegend(.hidden): plot height \(format(hidden.height)) pt")
}

// MARK: - §9 Cell area on the ground

let earthRadius = 6371.0088  // km, mean radius
let degrees = Double.pi / 180

/// Is the point inside the pointy-top hexagon of circumradius `r` around `c`?
func insideHexagon(_ px: Double, _ py: Double, cx: Double, cy: Double, r: Double) -> Bool {
    let dx = abs(px - cx), dy = abs(py - cy)
    let halfWidth = sqrt(3) / 2 * r
    return dx <= halfWidth && dy <= r - dx / sqrt(3)
}

/// Ground area in km² of the region `inside(longitude, latitude)` (degrees), by summing
/// cos φ dλ dφ over a fine grid of the given box.
func groundArea(longitudes: ClosedRange<Double>, latitudes: ClosedRange<Double>, inside: (Double, Double) -> Bool) -> Double {
    let steps = 1200
    let dLon = (longitudes.upperBound - longitudes.lowerBound) / Double(steps)
    let dLat = (latitudes.upperBound - latitudes.lowerBound) / Double(steps)
    var area = 0.0
    for i in 0 ..< steps { for j in 0 ..< steps {
        let lon = longitudes.lowerBound + (Double(i) + 0.5) * dLon
        let lat = latitudes.lowerBound + (Double(j) + 0.5) * dLat
        if inside(lon, lat) { area += cos(lat * degrees) * dLon * degrees * dLat * degrees }
    } }
    return area * earthRadius * earthRadius
}

func projectionReport() {
    print("\n9. Ground area of one cell (km²), numerically integrated")
    let standard = -41.0
    let k = cos(standard * degrees)
    // Cylindrical equal-area with standard parallel φ0: x = λ cos φ0, y = sin φ / cos φ0 (λ, φ in radians).
    func project(_ lon: Double, _ lat: Double) -> (Double, Double) { (lon * degrees * k, sin(lat * degrees) / k) }
    // A projected radius that gives the degree cell's area at the standard parallel.
    let projectedRadius = 0.3 * degrees
    for latitude in [-34.0, -41.0, -48.0] {
        let lonBox = 172.0 - 0.4 ... 172.0 + 0.4, latBox = latitude - 0.6 ... latitude + 0.6
        let plain = groundArea(longitudes: lonBox, latitudes: latBox) { insideHexagon($0, $1, cx: 172, cy: latitude, r: 0.3) }
        let c = project(172, latitude)
        let equal = groundArea(longitudes: lonBox, latitudes: latBox) { lon, lat in
            let p = project(lon, lat)
            return insideHexagon(p.0, p.1, cx: c.0, cy: c.1, r: projectedRadius)
        }
        // A degree cell's east-west extent on the ground, over a regular hexagon's of the same height.
        let squash = cos(latitude * degrees)
        let equalStretch = k / cos(latitude * degrees)
        print("   latitude \(format(latitude, 0))°: degree grid \(Int(plain.rounded())) km² (east-west ×\(format(squash, 2))), equal-area grid (φ0 = −41°) \(Int(equal.rounded())) km² (east-west ×\(format(equalStretch, 2)))")
    }
}

// MARK: - §10 Hexagons drawn as areas in data space

struct Band: Identifiable {
    let id: Int
    let x: Double, low: Double, high: Double
}

/// A pointy-top hexagon as three x-monotone band points: left edge, middle, right edge.
func bands(of cell: Cell, scale: Double = 1) -> [Band] {
    let r = radius * scale, half = sqrt(3) / 2 * r
    return [
        Band(id: 0, x: cell.x - half, low: cell.y - r / 2, high: cell.y + r / 2),
        Band(id: 1, x: cell.x, low: cell.y - r, high: cell.y + r),
        Band(id: 2, x: cell.x + half, low: cell.y - r / 2, high: cell.y + r / 2),
    ]
}

struct AreaHexChart: View {
    let cells: [Cell]
    let series: Bool
    var byCount = false
    var size = CGSize(width: 480, height: 360)

    var body: some View {
        Chart {
            ForEach(cells) { cell in
                ForEach(bands(of: cell)) { band in
                    if series {
                        AreaMark(x: .value("x", band.x), yStart: .value("Low", band.low), yEnd: .value("High", band.high), series: .value("Cell", cell.id))
                            .foregroundStyle(by: .value("Count", byCount ? 5 : cell.q))
                    } else {
                        AreaMark(x: .value("x", band.x), yStart: .value("Low", band.low), yEnd: .value("High", band.high))
                            .foregroundStyle(by: .value("Count", byCount ? 5 : cell.q))
                    }
                }
            }
        }
        .chartForegroundStyleScale(domain: -100 ... 100, range: Gradient(colors: [.black.opacity(0.5), .black.opacity(0.5)]))
        .chartXScale(domain: tileX, range: .plotDimension(padding: 0))
        .chartYScale(domain: tileY, range: .plotDimension(padding: 0))
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartLegend(.hidden)
        .frame(width: size.width, height: size.height)
        .background(Color.white)
    }
}

@MainActor func areaReport() {
    print("\n10. Hexagons as AreaMark(x:yStart:yEnd:series:) in data space, three points each")
    let matched = CGSize(width: 480, height: 360), squat = CGSize(width: 480, height: 300)
    print("   one series per cell, plot 480 × 360:".padding(toLength: 52, withPad: " ", startingAt: 0), percent(coverage(render("10-matched", AreaHexChart(cells: tileCells, series: true)), size: matched)))
    print("   one series per cell, plot 480 × 300:".padding(toLength: 52, withPad: " ", startingAt: 0), percent(coverage(render("10-squat", AreaHexChart(cells: tileCells, series: true, size: squat)), size: squat)))
    // Two cells far apart with the same count: ink halfway between them means one area.
    let pair = [Cell(q: -2, r: 0), Cell(q: 2, r: 0)]
    for series in [false, true] {
        let bitmap = render("10-pair-\(series)", AreaHexChart(cells: pair, series: series, byCount: true))
        let between = bitmap.gray(240, 180) < 0.9
        print("   two cells with the same count, \(series ? "series per cell:" : "no series:      ")".padding(toLength: 52, withPad: " ", startingAt: 0), between ? "joined into one area" : "two hexagons")
    }
}

// MARK: - §11 A size that follows the plot

/// Reads the plot size into state from `chartPlotStyle` and sizes every hexagon from it.
/// `composed` adds what the skill's recipe puts around it: axes shown, the plot's ratio
/// locked and the plot clipped.
struct FollowingChart: View {
    var composed = false
    var report: ((CGSize) -> Void)? = nil
    var onFrame: ((CGRect) -> Void)? = nil
    @State private var plotSize: CGSize = .zero

    var body: some View {
        Chart {
            PointPlot(tileCells, x: .value("x", \.x), y: .value("y", \.y))
                .symbol(Hexagon(unit: narrowUnit))
                .symbolSize(CGSize(width: plotSize.width / 16 * sqrt(3) * radius, height: plotSize.height / 12 * 2 * radius))
                .foregroundStyle(.black.opacity(0.5))
        }
        .chartXScale(domain: tileX, range: .plotDimension(padding: 0))
        .chartYScale(domain: tileY, range: .plotDimension(padding: 0))
        .chartXAxis(composed ? .automatic : .hidden)
        .chartYAxis(composed ? .automatic : .hidden)
        .chartPlotStyle { plot in
            locked(plot)
                .onGeometryChange(for: CGSize.self) { $0.size } action: { size in
                    plotSize = size
                    report?(size)
                }
        }
        .chartOverlay { proxy in PlotFrameReader(proxy: proxy) { onFrame?($0) } }
        .background(Color.white)
    }

    @ViewBuilder func locked(_ plot: ChartPlotContent) -> some View {
        if composed {
            plot.aspectRatio(16.0 / 12.0, contentMode: .fit).clipped()
        } else {
            plot
        }
    }
}

@MainActor func followingReport() {
    print("\n11. Size from the plot's geometry: onGeometryChange inside chartPlotStyle, into @State")
    var reported: [CGSize] = []
    let hosting = NSHostingView(rootView: FollowingChart { reported.append($0) })
    let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 480, height: 360), styleMask: [.borderless], backing: .buffered, defer: false)
    window.contentView = hosting
    hosting.layoutSubtreeIfNeeded()
    RunLoop.main.run(until: Date().addingTimeInterval(0.4))
    window.setContentSize(NSSize(width: 240, height: 180))
    hosting.layoutSubtreeIfNeeded()
    RunLoop.main.run(until: Date().addingTimeInterval(0.4))
    window.close()
    print("   hosted at 480 × 360, then resized to 240 × 180; plot sizes reported:", reported.map { "\(Int($0.width)) × \(Int($0.height))" }.joined(separator: ", "))
    let size = CGSize(width: 480, height: 360)
    let bitmap = render("11-image-renderer", FollowingChart().frame(width: size.width, height: size.height))
    print("   the same chart through ImageRenderer at 480 × 360:".padding(toLength: 64, withPad: " ", startingAt: 0), percent(coverage(bitmap, size: size)))

    var composedSize = CGSize.zero, plot = CGRect.zero
    host(FollowingChart(composed: true, report: { composedSize = $0 }, onFrame: { plot = $0 }).frame(width: 480, height: 480), size: CGSize(width: 480, height: 480))
    let composed = render("11-composed", FollowingChart(composed: true).frame(width: 480, height: 480))
    print("   axes shown, plot ratio locked and clipped, frame 480 × 480: plot \(format(plot.width)) × \(format(plot.height)) pt, reported \(format(composedSize.width)) × \(format(composedSize.height));",
          percent(coverage(composed, size: plot.size, origin: plot.origin)))
}

// MARK: - Run

_ = NSApplication.shared
MainActor.assumeIsolated {
    let arguments = CommandLine.arguments
    if let index = arguments.firstIndex(of: "--png"), index + 1 < arguments.count {
        pngDirectory = URL(fileURLWithPath: arguments[index + 1])
        try? FileManager.default.createDirectory(at: pngDirectory!, withIntermediateDirectories: true)
    }
    print("Swift Charts hexagon probe — \(ProcessInfo.processInfo.operatingSystemVersionString)\n")
    let proportion = symbolReport()
    tilingReport(heightPerRootArea: proportion.heightPerRootArea)
    domainReport()
    edgeReport()
    binningReport()
    colorReport()
    legendReport()
    projectionReport()
    areaReport()
    followingReport()
}
