from __future__ import annotations

import importlib.util
import inspect
import io
import re
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "swift-charts-hexagonal-heatmap"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


heatmap_scan = load("heatmap_scan", SKILL / "scripts" / "heatmap_scan.py")
charts_scan = load("charts_scan_shared", ROOT / "skills" / "swift-charts-dynamic-masking" / "scripts" / "charts_scan.py")

HEADER = """
import Charts
import SwiftUI

struct Bin: Identifiable { let id: Int; let x: Double; let y: Double; let count: Int }

struct Hexagon: ChartSymbolShape {
    var perceptualUnitRect: CGRect { CGRect(x: 0.067, y: 0, width: 0.866, height: 1) }
    func path(in rect: CGRect) -> Path { Path(rect) }
}
"""

GOOD_MODIFIERS = """
.chartXScale(domain: xDomain, range: .plotDimension(padding: 0))
.chartYScale(domain: yDomain, range: .plotDimension(padding: 0))
.chartForegroundStyleScale(domain: 0 ... 10, range: Gradient(colors: [.blue, .red]), type: .symmetricLog(slopeAtZero: 1))
.chartPlotStyle { $0.aspectRatio(4 / 3, contentMode: .fit).clipped() }
"""


class ScanTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)

    def tearDown(self) -> None:
        self._directory.cleanup()

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def rules(self, body: str) -> list[str]:
        self.write("Sources/Heatmap.swift", HEADER + textwrap.dedent(body))
        return sorted(finding["rule"] for finding in heatmap_scan.scan(self.root)["findings"])

    def assertRules(self, body: str, expected: list[str]) -> None:
        self.assertEqual(self.rules(body), sorted(expected))


def view(chart: str, modifiers: str = GOOD_MODIFIERS, extra: str = "") -> str:
    """A view whose body is `Chart { chart }` followed by `modifiers`."""
    return (
        "struct V: View {\n"
        "    let bins: [Bin]\n"
        "    let xDomain = 0.0 ... 16.0\n"
        "    let yDomain = 0.0 ... 12.0\n"
        "    var cell: CGSize = .zero\n"
        f"{textwrap.indent(textwrap.dedent(extra), '    ')}\n"
        "    var body: some View {\n"
        "        Chart {\n"
        f"{textwrap.indent(textwrap.dedent(chart), '            ')}\n"
        "        }\n"
        f"{textwrap.indent(textwrap.dedent(modifiers), '        ')}\n"
        "    }\n"
        "}\n"
    )


POINTS = """
ForEach(bins) { bin in
    PointMark(x: .value("x", bin.x), y: .value("y", bin.y))
        .symbol(Hexagon())
        .symbolSize(cell)
        .foregroundStyle(by: .value("Count", bin.count))
}
"""


class SizeTests(ScanTestCase):
    def test_area_from_the_cell_width(self) -> None:
        chart = POINTS.replace(".symbolSize(cell)", ".symbolSize(width * width * 0.92)")
        self.assertRules(view(chart, extra="var width: CGFloat { 20 }"), ["HEX001"])

    def test_size_scale_value(self) -> None:
        chart = POINTS.replace(".symbolSize(cell)", '.symbolSize(by: .value("Cell", 1))')
        self.assertRules(view(chart), ["HEX001"])

    def test_cgsize_property(self) -> None:
        self.assertRules(view(POINTS), [])

    def test_cgsize_literal_and_function(self) -> None:
        literal = POINTS.replace(".symbolSize(cell)", ".symbolSize(CGSize(width: 30, height: 34))")
        self.assertRules(view(literal), [])
        call = POINTS.replace(".symbolSize(cell)", ".symbolSize(grid.size(in: plot))")
        extra = "func size(in plot: CGSize) -> CGSize { plot }"
        self.assertRules(view(call, extra=extra), [])

    def test_area_in_a_hexagon_content_type(self) -> None:
        content = """
        struct Cells: ChartContent {
            let bins: [Bin]
            let area: CGFloat
            var body: some ChartContent {
                PointPlot(bins, x: .value("x", \\Bin.x), y: .value("y", \\Bin.y))
                    .symbol(Hexagon())
                    .symbolSize(area)
            }
        }
        """
        self.assertRules(content + view("Cells(bins: bins, area: 400)"), ["HEX001"])

    def test_shape_found_by_its_six_corners(self) -> None:
        shape = """
        struct Cellular: ChartSymbolShape {
            var perceptualUnitRect: CGRect { CGRect(x: 0, y: 0, width: 1, height: 1) }
            func path(in rect: CGRect) -> Path {
                var path = Path()
                path.addLines([CGPoint(x: 0, y: 0), CGPoint(x: 1, y: 0), CGPoint(x: 1, y: 1),
                               CGPoint(x: 0, y: 1), CGPoint(x: 0, y: 2), CGPoint(x: 1, y: 2)])
                return path
            }
        }
        """
        chart = POINTS.replace("Hexagon()", "Cellular()").replace(".symbolSize(cell)", ".symbolSize(400)")
        self.assertRules(shape + view(chart), ["HEX001"])

    def test_other_symbols_are_ignored(self) -> None:
        chart = POINTS.replace("Hexagon()", ".circle").replace(".symbolSize(cell)", ".symbolSize(400)")
        self.assertRules(view(chart, modifiers=""), [])


class PlotTests(ScanTestCase):
    def test_automatic_domains(self) -> None:
        modifiers = GOOD_MODIFIERS.replace(".chartYScale(domain: yDomain, range: .plotDimension(padding: 0))\n", "")
        self.assertRules(view(POINTS, modifiers), ["HEX002"])

    def test_not_clipped(self) -> None:
        modifiers = GOOD_MODIFIERS.replace(".clipped()", "")
        self.assertRules(view(POINTS, modifiers), ["HEX003"])

    def test_ratio_on_the_chart_with_axes(self) -> None:
        modifiers = GOOD_MODIFIERS.replace(".aspectRatio(4 / 3, contentMode: .fit)", "") + ".aspectRatio(4 / 3, contentMode: .fit)\n"
        self.assertRules(view(POINTS, modifiers), ["HEX009"])

    def test_ratio_on_the_chart_without_axes(self) -> None:
        modifiers = (
            GOOD_MODIFIERS.replace(".aspectRatio(4 / 3, contentMode: .fit)", "")
            + ".chartXAxis(.hidden)\n.chartYAxis(.hidden)\n.aspectRatio(4 / 3, contentMode: .fit)\n"
        )
        self.assertRules(view(POINTS, modifiers), [])


class ColorTests(ScanTestCase):
    def test_linear_gradient_scale(self) -> None:
        modifiers = GOOD_MODIFIERS.replace(", type: .symmetricLog(slopeAtZero: 1)", "")
        self.assertRules(view(POINTS, modifiers), ["HEX006"])

    def test_explicit_linear(self) -> None:
        modifiers = GOOD_MODIFIERS.replace(".symmetricLog(slopeAtZero: 1)", ".linear")
        self.assertRules(view(POINTS, modifiers), ["HEX006"])

    def test_legend_hidden(self) -> None:
        self.assertRules(view(POINTS, GOOD_MODIFIERS + ".chartLegend(.hidden)\n"), ["HEX007"])

    def test_legend_hidden_without_a_color_scale(self) -> None:
        chart = POINTS.replace('.foregroundStyle(by: .value("Count", bin.count))', ".foregroundStyle(.blue)")
        self.assertRules(view(chart, GOOD_MODIFIERS + ".chartLegend(.hidden)\n"), [])


AREAS = """
ForEach(bins) { bin in
    ForEach(bands(of: bin)) { band in
        AreaMark(x: .value("x", band.x), yStart: .value("Bottom", band.bottom), yEnd: .value("Top", band.top)SERIES)
            .foregroundStyle(by: .value("Count", bin.count))
    }
}
"""


class AreaTests(ScanTestCase):
    def test_area_cells_without_series(self) -> None:
        self.assertRules(view(AREAS.replace("SERIES", "")), ["HEX008"])

    def test_area_cells_with_series(self) -> None:
        self.assertRules(view(AREAS.replace("SERIES", ', series: .value("Cell", bin.id)')), [])

    def test_a_single_range_band_is_not_a_hexagon_chart(self) -> None:
        chart = """
        ForEach(bins) { bin in
            AreaMark(x: .value("x", bin.x), yStart: .value("Low", bin.y - 1), yEnd: .value("High", bin.y + 1))
        }
        """
        self.assertRules(view(chart, modifiers=""), [])


class BinningTests(ScanTestCase):
    def test_grouping_in_a_computed_property(self) -> None:
        extra = """
        let points: [CGPoint]
        var grouped: [Int: [CGPoint]] { Dictionary(grouping: points) { Int($0.x) } }
        """
        self.assertRules(view(POINTS, extra=extra), ["HEX004"])

    def test_binning_function_called_from_body(self) -> None:
        helper = """
        func bins(_ points: [CGPoint]) -> [Bin] {
            var counts: [Int: Int] = [:]
            for point in points { counts[Int(point.x), default: 0] += 1 }
            return counts.map { Bin(id: $0.key, x: 0, y: 0, count: $0.value) }
        }
        """
        chart = POINTS.replace("ForEach(bins)", "ForEach(bins(points))")
        self.assertRules(helper + view(chart, extra="let points: [CGPoint]"), ["HEX004"])

    def test_binning_in_task_or_init(self) -> None:
        helper = """
        func bins(_ points: [CGPoint]) -> [Bin] {
            Dictionary(grouping: points) { Int($0.x) }.map { Bin(id: $0.key, x: 0, y: 0, count: $0.value.count) }
        }
        """
        extra = """
        let points: [CGPoint]
        @State private var cached: [Bin] = []
        init(points: [CGPoint]) {
            self.points = points
            self.bins = bins(points)
        }
        """
        chart = POINTS + "\n"
        modifiers = GOOD_MODIFIERS + ".task { cached = bins(points) }\n"
        self.assertRules(helper + view(chart, modifiers, extra), [])

    def test_independent_rounding(self) -> None:
        code = """
        func cell(x: Double, y: Double, radius: Double) -> (Int, Int) {
            let q = (sqrt(3) / 3 * x - y / 3) / radius
            let r = (2 * y / 3) / radius
            return (Int(q.rounded()), Int(r.rounded()))
        }
        """
        self.assertRules(code, ["HEX005"])

    def test_independent_rounding_in_a_helper(self) -> None:
        code = """
        func rounded(q: Double, r: Double) -> (Int, Int) {
            (Int(q.rounded()), Int(r.rounded()))
        }
        """
        self.assertRules(code, ["HEX005"])

    def test_cube_rounding(self) -> None:
        code = """
        func nearest(q: Double, r: Double) -> (Int, Int) {
            let s = -q - r
            var rq = q.rounded(), rr = r.rounded()
            let rs = s.rounded()
            if abs(rq - q) > abs(rr - r), abs(rq - q) > abs(rs - s) { rq = -rr - rs }
            else if abs(rr - r) > abs(rs - s) { rr = -rq - rs }
            return (Int(rq), Int(rr))
        }
        func cell(x: Double, y: Double, radius: Double) -> (Int, Int) {
            nearest(q: (x * 3.squareRoot() / 3 - y / 3) / radius, r: (2 * y / 3) / radius)
        }
        """
        self.assertRules(code, [])


class ProjectTests(ScanTestCase):
    def test_deployment_targets_and_shapes(self) -> None:
        self.write("App.xcodeproj/project.pbxproj", "IPHONEOS_DEPLOYMENT_TARGET = 17.0;\n")
        self.write("Package.swift", "platforms: [.iOS(.v16)]")
        self.write("Sources/Heatmap.swift", HEADER + view(POINTS))
        report = heatmap_scan.scan(self.root)
        self.assertEqual(report["project"]["ios_deployment_targets"], ["16.0", "17.0"])
        self.assertEqual(report["project"]["hexagon_shapes"], ["Hexagon"])
        self.assertEqual(report["project"]["files_with_hexagon_charts"], ["Sources/Heatmap.swift"])

    def test_dependencies_are_skipped(self) -> None:
        chart = POINTS.replace(".symbolSize(cell)", ".symbolSize(400)")
        self.write("Pods/Vendor/Heatmap.swift", HEADER + view(chart))
        self.assertEqual(heatmap_scan.scan(self.root)["findings"], [])
        self.assertTrue(heatmap_scan.scan(self.root, include_dependencies=True)["findings"])

    def test_scan_does_not_modify_files(self) -> None:
        path = self.write("Sources/Heatmap.swift", HEADER + view(POINTS, modifiers=""))
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        with redirect_stdout(io.StringIO()):
            heatmap_scan.main([str(self.root), "--format", "markdown"])
            heatmap_scan.main([str(self.root), "--format", "json"])
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_inventory(self) -> None:
        self.write("Sources/Heatmap.swift", HEADER + view(POINTS))
        inventory = heatmap_scan.scan(self.root)["inventory"]
        self.assertEqual(inventory["Chart"], 1)
        self.assertEqual(inventory["PointMark"], 1)
        self.assertEqual(inventory["symmetricLog"], 1)


class OwnAdviceTests(ScanTestCase):
    """The skill's own recommended code must scan clean."""

    def test_reference_samples_have_no_findings_above_info(self) -> None:
        blocks: list[str] = []
        for path in sorted((SKILL / "references").glob("*.md")):
            blocks += re.findall(r"```swift\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
        self.assertGreaterEqual(len(blocks), 6)
        for index, block in enumerate(blocks, start=1):
            self.write(f"Sample{index}/Sample.swift", block)
        report = heatmap_scan.scan(self.root)
        self.assertGreaterEqual(len(report["project"]["files_with_hexagon_charts"]), 3)
        findings = [f for f in report["findings"] if f["severity"] != "info"]
        self.assertEqual(findings, [])


class SharedCodeTests(unittest.TestCase):
    """The parsing helpers are copied from charts_scan.py; they must not drift."""

    SHARED = [
        "Finding", "Call", "strip_comments", "blank_strings", "matching", "split_arguments", "parse_call",
        "line_of", "chart_blocks", "deployment_targets", "iter_project_files", "read_text", "relative", "make_finding",
    ]

    def test_helpers_match_the_masking_scanner(self) -> None:
        for name in self.SHARED:
            with self.subTest(name):
                self.assertEqual(inspect.getsource(getattr(heatmap_scan, name)), inspect.getsource(getattr(charts_scan, name)))
        for name in ("SEVERITIES", "EXCLUDED_DIRS", "DEPENDENCY_DIRS"):
            with self.subTest(name):
                self.assertEqual(getattr(heatmap_scan, name), getattr(charts_scan, name))
        self.assertEqual(heatmap_scan.CHART_OPEN.pattern, charts_scan.CHART_OPEN.pattern)


class RuleMetadataTests(unittest.TestCase):
    def test_every_rule_cites_a_source(self) -> None:
        pattern = re.compile(
            r"WWDC2\d \d{5,6} .+ \d+:\d\d"
            r"|Apple documentation › "
            r"|Measured: scripts/probes/hexagon_probe\.swift"
        )
        for rule in heatmap_scan.RULES.values():
            with self.subTest(rule.id):
                self.assertRegex(rule.source, pattern)
                self.assertIn(rule.severity, heatmap_scan.SEVERITIES)

    def test_every_rule_is_listed_in_checks(self) -> None:
        checks = (ROOT / "CHECKS.md").read_text(encoding="utf-8")
        for rule_id in heatmap_scan.RULES:
            with self.subTest(rule_id):
                self.assertIn(rule_id, checks)


if __name__ == "__main__":
    unittest.main()
