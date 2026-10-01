// Re-derives every "Measured" statement in the swift-charts-dynamic-masking skill.
//
//   xcrun swiftc -O -suppress-warnings scripts/probes/masking_probe.swift -o "$TMPDIR/masking_probe"
//   "$TMPDIR/masking_probe" [--png <directory>]
//
// It renders small charts on macOS with ImageRenderer, compares them pixel by pixel,
// and hosts one chart in an offscreen window to read what ChartProxy reports. The
// charts have no axes and fixed scales, so every point's pixel position is known.
// Swift Charts is the same framework on iOS and macOS; the measurements are of chart
// layout and masking, not of anything platform specific.

import AppKit
import Charts
import SwiftUI

struct Sample: Identifiable {
    let id: Int
    let day: Date
    let value: Double
}

let width = 400.0, height = 240.0, edgePadding = 16.0
let base = Date(timeIntervalSinceReferenceDate: 800_000_000)
let values: [Double] = [40, 70, 30, 95, 75, 55, 100]
let samples = values.enumerated().map {
    Sample(id: $0.offset, day: base.addingTimeInterval(Double($0.offset) * 86_400), value: $0.element)
}
let first = samples.first!.day, last = samples.last!.day
let padded = first.addingTimeInterval(-43_200) ... last.addingTimeInterval(43_200)

func describe(_ date: Date) -> String {
    if date == first { return "the first point" }
    if date == last { return "the last point" }
    if date < first { return String(format: "%.1f h before the first point", first.timeIntervalSince(date) / 3600) }
    if date > last { return String(format: "%.1f h after the last point", date.timeIntervalSince(last) / 3600) }
    return "inside the data"
}

enum Scale { case paddedRange, paddedDomain, automatic }

enum Layers {
    case plot(lineWidth: CGFloat = 3, symbols: Bool = false)
    case twoPlots(series: Bool, sameStyle: Bool = true)
    case twoMarkLines(series: Bool)
    /// Days 0–3 solid and days 4–6 dashed, as two plots: the shape of an actual/forecast split.
    case split(series: Bool)
    /// Two different collections, flat at 20 and at 80.
    case twoCollections(series: Bool)
    case masked(start: Date?, end: Date?, vectorized: Bool = false)
    case rule(at: Date)
}

struct ProbeChart: View {
    let layers: Layers
    var scale: Scale = .paddedRange
    var onProxy: ((ChartProxy, CGRect) -> Void)? = nil

    @ChartContentBuilder var content: some ChartContent {
        switch layers {
        case let .plot(lineWidth, symbols): line(lineWidth: lineWidth, symbols: symbols)
        case let .twoPlots(series, sameStyle): twoPlots(series: series, sameStyle: sameStyle)
        case let .twoMarkLines(series): twoMarkLines(series: series)
        case let .split(series): split(series: series)
        case let .twoCollections(series): twoCollections(series: series)
        case let .masked(start, end, vectorized): masked(start: start, end: end, vectorized: vectorized)
        case let .rule(date):
            line(lineWidth: 3, symbols: false)
            RuleMark(x: .value("Selected", date))
        }
    }

    @ChartContentBuilder func line(lineWidth: CGFloat, symbols: Bool) -> some ChartContent {
        let plot = LinePlot(samples, x: .value("Day", \.day), y: .value("Value", \.value))
            .foregroundStyle(.black)
            .lineStyle(StrokeStyle(lineWidth: lineWidth))
        if symbols {
            plot.symbol(.circle).symbolSize(150)
        } else {
            plot
        }
    }

    @ChartContentBuilder func twoPlots(series: Bool, sameStyle: Bool) -> some ChartContent {
        if series {
            LinePlot(samples, x: .value("Day", \.day), y: .value("Value", \.value), series: .value("Layer", "Dimmed"))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
            LinePlot(samples, x: .value("Day", \.day), y: .value("Value", \.value), series: .value("Layer", "Active"))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
        } else {
            LinePlot(samples, x: .value("Day", \.day), y: .value("Value", \.value))
                .foregroundStyle(sameStyle ? Color.black : Color(white: 0.01)).lineStyle(StrokeStyle(lineWidth: 3))
            LinePlot(samples, x: .value("Day", \.day), y: .value("Value", \.value))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
        }
    }

    @ChartContentBuilder func twoMarkLines(series: Bool) -> some ChartContent {
        ForEach(samples) { sample in
            LineMark(x: .value("Day", sample.day), y: .value("Value", sample.value), series: .value("Layer", series ? "Dimmed" : "Same"))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
        }
        ForEach(samples) { sample in
            LineMark(x: .value("Day", sample.day), y: .value("Value", sample.value), series: .value("Layer", series ? "Active" : "Same"))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
        }
    }

    @ChartContentBuilder func split(series: Bool) -> some ChartContent {
        LinePlot(Array(samples[0 ... 3]), x: .value("Day", \.day), y: .value("Value", \.value), series: .value("Part", series ? "Actual" : "Same"))
            .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
        LinePlot(Array(samples[4 ... 6]), x: .value("Day", \.day), y: .value("Value", \.value), series: .value("Part", series ? "Forecast" : "Same"))
            .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3, dash: [6, 6]))
    }

    @ChartContentBuilder func twoCollections(series: Bool) -> some ChartContent {
        let low = samples.map { Sample(id: $0.id, day: $0.day, value: 20) }
        let high = samples.map { Sample(id: $0.id, day: $0.day, value: 80) }
        if series {
            LinePlot(low, x: .value("Day", \.day), y: .value("Value", \.value), series: .value("Line", "Low"))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
            LinePlot(high, x: .value("Day", \.day), y: .value("Value", \.value), series: .value("Line", "High"))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
        } else {
            LinePlot(low, x: .value("Day", \.day), y: .value("Value", \.value))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
            LinePlot(high, x: .value("Day", \.day), y: .value("Value", \.value))
                .foregroundStyle(.black).lineStyle(StrokeStyle(lineWidth: 3))
        }
    }

    @ChartContentBuilder func masked(start: Date?, end: Date?, vectorized: Bool) -> some ChartContent {
        line(lineWidth: 5, symbols: true)
            .mask {
                if let start, let end {
                    if vectorized {
                        RectanglePlot(samples, xStart: .value("Start", start), xEnd: .value("End", end))
                    } else {
                        RectangleMark(xStart: .value("Start", start), xEnd: .value("End", end))
                    }
                } else {
                    RectangleMark(xStart: nil, xEnd: nil, yStart: nil, yEnd: nil)
                }
            }
    }

    var body: some View {
        scaled(
            Chart { content }
                .chartXAxis(.hidden)
                .chartYAxis(.hidden)
                .chartYScale(domain: 0 ... 100)
                .chartOverlay { proxy in overlay(proxy) }
        )
        .frame(width: CGFloat(width), height: CGFloat(height))
        .background(Color.white)
    }

    func overlay(_ proxy: ChartProxy) -> some View {
        GeometryReader { geometry in
            Color.clear.onAppear {
                if let frame = proxy.plotFrame { onProxy?(proxy, geometry[frame]) }
            }
        }
    }

    @ViewBuilder func scaled(_ chart: some View) -> some View {
        switch scale {
        case .paddedRange:
            chart.chartXScale(domain: first ... last, range: .plotDimension(startPadding: CGFloat(edgePadding), endPadding: CGFloat(edgePadding)))
        case .paddedDomain:
            chart.chartXScale(domain: padded)
        case .automatic:
            chart
        }
    }
}

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

    /// Top-left origin, like SwiftUI.
    func isDark(_ x: Int, _ y: Int) -> Bool {
        let index = (y * width + x) * 4
        return Int(pixels[index]) + Int(pixels[index + 1]) + Int(pixels[index + 2]) < 3 * 128
    }

    func darkPixels(columns: Range<Int>) -> Int {
        var count = 0
        for y in 0 ..< height { for x in columns where isDark(x, y) { count += 1 } }
        return count
    }

    func differing(from other: Bitmap) -> Int {
        var count = 0
        for y in 0 ..< height { for x in 0 ..< width where isDark(x, y) != other.isDark(x, y) { count += 1 } }
        return count
    }

    /// Any dark pixel within `radius` of the point.
    func inked(near point: CGPoint, radius: Int = 2) -> Bool {
        for dy in -radius ... radius { for dx in -radius ... radius where isDark(Int(point.x) + dx, Int(point.y) + dy) { return true } }
        return false
    }
}

@MainActor var pngDirectory: URL?

@MainActor func render(_ name: String, _ chart: ProbeChart) -> Bitmap {
    let renderer = ImageRenderer(content: chart)
    renderer.scale = 1
    let image = renderer.cgImage!
    if let pngDirectory {
        let data = NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:])!
        try? data.write(to: pngDirectory.appendingPathComponent("\(name).png"))
    }
    return Bitmap(image)
}

/// Pixel position of sample `index` on the padded-range scale.
func point(_ index: Int) -> CGPoint {
    let x = edgePadding + (width - 2 * edgePadding) * Double(index) / Double(samples.count - 1)
    return CGPoint(x: x, y: height - height * values[index] / 100)
}

/// The middle of a straight segment from the last point back to the first. The data's
/// own line passes through (200, 24) there, so ink at this spot can only be a join.
let joinProbe = CGPoint(x: (point(0).x + point(6).x) / 2, y: (point(0).y + point(6).y) / 2)

@MainActor func report() {
    print("Swift Charts masking probe — \(ProcessInfo.processInfo.operatingSystemVersionString)")
    print("Chart \(Int(width))×\(Int(height)) pt, \(samples.count) daily points, x range padded \(Int(edgePadding)) pt each side\n")

    print("1. Two copies of the same line")
    let joins: [(String, ProbeChart)] = [
        ("LinePlot ×2, no series:", ProbeChart(layers: .twoPlots(series: false))),
        ("LinePlot ×2, distinct series:", ProbeChart(layers: .twoPlots(series: true))),
        ("LinePlot ×2, no series, other color:", ProbeChart(layers: .twoPlots(series: false, sameStyle: false))),
        ("LineMark ×2, same series:", ProbeChart(layers: .twoMarkLines(series: false))),
        ("LineMark ×2, distinct series:", ProbeChart(layers: .twoMarkLines(series: true))),
    ]
    for (index, (label, chart)) in joins.enumerated() {
        let joined = render("1-\(index)", chart).inked(near: joinProbe)
        print("   \(label.padding(toLength: 44, withPad: " ", startingAt: 0)) \(joined ? "joined last → first" : "not joined")")
    }
    for series in [false, true] {
        let bitmap = render("1-collections-\(series)", ProbeChart(layers: .twoCollections(series: series)))
        // Merged, the line runs from the low line's last point to the high line's first.
        let joined = bitmap.inked(near: CGPoint(x: point(3).x, y: height - height * 0.5))
        let label = "Two collections (20 and 80), \(series ? "distinct series:" : "no series:")"
        print("   \(label.padding(toLength: 44, withPad: " ", startingAt: 0)) \(joined ? "joined into one line" : "two lines")")
    }
    for series in [false, true] {
        let bitmap = render("1-split-\(series)", ProbeChart(layers: .split(series: series)))
        // Ink in the empty stretch between day 3 and day 4 means the halves are one line.
        let middle = CGPoint(x: (point(3).x + point(4).x) / 2, y: (point(3).y + point(4).y) / 2)
        let connected = bitmap.inked(near: middle)
        // A 6-on, 6-off dash leaves about half the columns of the dashed half without ink.
        var inked = 0, total = 0
        for x in Int(point(4).x) + 6 ..< Int(point(6).x) - 6 {
            let t = (Double(x) - point(4).x) / (point(5).x - point(4).x)
            let (a, b) = t <= 1 ? (point(4), point(5)) : (point(5), point(6))
            let u = t <= 1 ? t : (Double(x) - point(5).x) / (point(6).x - point(5).x)
            total += 1
            if bitmap.inked(near: CGPoint(x: Double(x), y: a.y + (b.y - a.y) * u), radius: 1) { inked += 1 }
        }
        let coverage = Double(inked) / Double(total)
        let label = "Days 0–3 solid + 4–6 dashed, \(series ? "distinct series:" : "no series:")"
        print("   \(label.padding(toLength: 44, withPad: " ", startingAt: 0)) \(connected ? "connected across the split" : "gap at the split"), second half \(coverage > 0.85 ? "solid" : "dashed") (\(Int(coverage * 100))% inked)")
    }

    print("\n2. Where the mask starts and ends (line width 5, circle symbols)")
    let plain = render("2-unmasked", ProbeChart(layers: .plot(lineWidth: 5, symbols: true)))
    let edges = 0 ..< Int(point(0).x)
    let ends = Int(point(6).x) + 1 ..< Int(width)
    func clipped(_ bitmap: Bitmap) -> String {
        let lost = plain.darkPixels(columns: edges) - bitmap.darkPixels(columns: edges)
        let lostEnd = plain.darkPixels(columns: ends) - bitmap.darkPixels(columns: ends)
        return "\(bitmap.differing(from: plain)) px differ from unmasked; \(lost) px lost left of the first point, \(lostEnd) right of the last"
    }
    print("   RectangleMark first…last:          ", clipped(render("2-first-last", ProbeChart(layers: .masked(start: first, end: last)))))
    print("   RectanglePlot first…last:          ", clipped(render("2-first-last-plot", ProbeChart(layers: .masked(start: first, end: last, vectorized: true)))))
    print("   RectangleMark, all edges nil:      ", clipped(render("2-whole-plot", ProbeChart(layers: .masked(start: nil, end: nil)))))
    print("   RectangleMark a week past the data:", clipped(render("2-past", ProbeChart(layers: .masked(start: first.addingTimeInterval(-604_800), end: last.addingTimeInterval(604_800))))))
    let paddedPlain = render("2-padded-unmasked", ProbeChart(layers: .plot(lineWidth: 5, symbols: true), scale: .paddedDomain))
    let paddedMasked = render("2-padded-masked", ProbeChart(layers: .masked(start: padded.lowerBound, end: padded.upperBound), scale: .paddedDomain))
    print("   Padded domain, mask domain bounds:  \(paddedMasked.differing(from: paddedPlain)) px differ from unmasked")

    print("\n3. Do marks outside the data move an automatic x domain?")
    var domains: [String: String] = [:]
    func domain(_ key: String) -> (ChartProxy, CGRect) -> Void {
        { proxy, _ in
            let domain = proxy.xDomain(dataType: Date.self)
            domains[key] = domain.count == 2 ? "\(describe(domain[0])) … \(describe(domain[1]))" : "\(domain)"
        }
    }
    let probes: [(String, ProbeChart)] = [
        ("Line only", ProbeChart(layers: .plot(), scale: .automatic, onProxy: domain("Line only"))),
        ("Mask a week past both ends", ProbeChart(layers: .masked(start: first.addingTimeInterval(-604_800), end: last.addingTimeInterval(604_800)), scale: .automatic, onProxy: domain("Mask a week past both ends"))),
        ("RuleMark 18 h after the last point", ProbeChart(layers: .rule(at: last.addingTimeInterval(64_800)), scale: .automatic, onProxy: domain("RuleMark 18 h after the last point"))),
        ("Same rule, explicit domain", ProbeChart(layers: .rule(at: last.addingTimeInterval(64_800)), onProxy: domain("Same rule, explicit domain"))),
    ]
    for (label, chart) in probes {
        host(chart)
        print("   \(label.padding(toLength: 36, withPad: " ", startingAt: 0)) x domain: \(domains[label] ?? "not reported")")
    }

    print("\n4. What a selection can be (x range padded; ChartProxy.value(atX:), then selectXValue)")
    for x in [0.0, -30.0, width + 30] {
        var selection: Date?
        host(ProbeChart(layers: .plot()) { proxy, plot in
            selection = proxy.value(atX: x - plot.minX, as: Date.self)
        })
        print("   x = \(Int(x)) pt:".padding(toLength: 16, withPad: " ", startingAt: 0), selection.map(describe) ?? "nil")
    }
    var selected: Date?
    let bound = Binding<Date?>(get: { selected }, set: { selected = $0 })
    host(AnyView(ProbeChart(layers: .plot()) { proxy, _ in proxy.selectXValue(at: -30) }.chartXSelection(value: bound)))
    print("   selectXValue(at: -30) → chartXSelection binding:", selected.map(describe) ?? "nil")
}

/// Four points at days 0, 1, 5 and 6, colored red, green, blue, black.
let uneven = [(0, NSColor.red), (1, NSColor.green), (5, NSColor.blue), (6, NSColor.black)].enumerated().map {
    (sample: Sample(id: $0.offset, day: base.addingTimeInterval(Double($0.element.0) * 86_400), value: 50), color: $0.element.1)
}

/// Padded by half a day, so the plot area is wider than the line: a gradient spanning
/// the plot would put its stops somewhere else than one spanning the line.
let unevenDomain = uneven.first!.sample.day.addingTimeInterval(-43_200) ... uneven.last!.sample.day.addingTimeInterval(43_200)

struct GradientChart: View {
    let stops: [Gradient.Stop]
    var body: some View {
        Chart {
            LinePlot(uneven.map(\.sample), x: .value("Day", \.day), y: .value("Value", \.value))
                .foregroundStyle(LinearGradient(stops: stops, startPoint: .leading, endPoint: .trailing))
                .lineStyle(StrokeStyle(lineWidth: 20))
        }
        .chartXScale(domain: unevenDomain)
        .chartYScale(domain: 0 ... 100)
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .frame(width: CGFloat(width), height: 100)
        .background(Color.white)
    }
}

@MainActor func gradientReport() {
    print("\n5. Gradient stops on unevenly spaced points (days 0, 1, 5, 6 → red, green, blue, black; domain padded 12 h)")
    let span = uneven.last!.sample.day.timeIntervalSince(uneven.first!.sample.day)
    let variants: [(String, [Gradient.Stop])] = [
        ("stops by index:", uneven.enumerated().map { Gradient.Stop(color: Color(nsColor: $0.element.color), location: Double($0.offset) / Double(uneven.count - 1)) }),
        ("stops by position between first and last day:", uneven.map { Gradient.Stop(color: Color(nsColor: $0.color), location: $0.sample.day.timeIntervalSince(uneven.first!.sample.day) / span) }),
    ]
    for (label, stops) in variants {
        let renderer = ImageRenderer(content: GradientChart(stops: stops))
        renderer.scale = 1
        let bitmap = NSBitmapImageRep(cgImage: renderer.cgImage!)
        var verdicts: [String] = []
        for (sample, expected) in uneven {
            // Sample just inside the line, 4 pt from the point, toward the middle of the chart.
            let domainSpan = unevenDomain.upperBound.timeIntervalSince(unevenDomain.lowerBound)
            let x = Int((width - 1) * sample.day.timeIntervalSince(unevenDomain.lowerBound) / domainSpan)
            let inset = x < Int(width) / 2 ? 4 : -4
            let color = bitmap.colorAt(x: x + inset, y: 50)!.usingColorSpace(.sRGB)!
            let target = expected.usingColorSpace(.sRGB)!
            let distance = abs(color.redComponent - target.redComponent) + abs(color.greenComponent - target.greenComponent) + abs(color.blueComponent - target.blueComponent)
            verdicts.append("day \(Int(sample.day.timeIntervalSince(base) / 86_400)) \(distance < 0.45 ? "on color" : "off by \(String(format: "%.2f", distance))")")
        }
        print("   \(label.padding(toLength: 48, withPad: " ", startingAt: 0)) \(verdicts.joined(separator: ", "))")
    }
}

@MainActor func host(_ view: some View) {
    let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: width, height: height), styleMask: [.borderless], backing: .buffered, defer: false)
    window.contentView = NSHostingView(rootView: view)
    window.contentView?.layoutSubtreeIfNeeded()
    RunLoop.main.run(until: Date().addingTimeInterval(0.4))
    window.close()
}

_ = NSApplication.shared
MainActor.assumeIsolated {
    let arguments = CommandLine.arguments
    if let index = arguments.firstIndex(of: "--png"), index + 1 < arguments.count {
        pngDirectory = URL(fileURLWithPath: arguments[index + 1])
        try? FileManager.default.createDirectory(at: pngDirectory!, withIntermediateDirectories: true)
    }
    report()
    gradientReport()
}
