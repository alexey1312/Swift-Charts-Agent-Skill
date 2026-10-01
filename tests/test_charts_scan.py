from __future__ import annotations

import importlib.util
import io
import re
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "swift-charts-dynamic-masking"
SPEC = importlib.util.spec_from_file_location("charts_scan", SKILL / "scripts" / "charts_scan.py")
assert SPEC and SPEC.loader
charts_scan = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = charts_scan
SPEC.loader.exec_module(charts_scan)

HEADER = """
import Charts
import SwiftUI

struct Day: Identifiable { let id = UUID(); let date: Date; let steps: Double }
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
        self.write("Sources/Chart.swift", HEADER + textwrap.dedent(body))
        return sorted(finding["rule"] for finding in charts_scan.scan(self.root)["findings"])

    def assertRules(self, body: str, expected: list[str]) -> None:
        self.assertEqual(self.rules(body), sorted(expected))


def view(chart: str, modifiers: str = "", extra: str = "") -> str:
    """A view whose body is `Chart { chart }` followed by `modifiers`."""
    return (
        "struct V: View {\n"
        "    let days: [Day]\n"
        "    @State private var picked: Date?\n"
        f"{textwrap.indent(textwrap.dedent(extra), '    ')}\n"
        "    var body: some View {\n"
        "        Chart {\n"
        f"{textwrap.indent(textwrap.dedent(chart), '            ')}\n"
        "        }\n"
        f"{textwrap.indent(textwrap.dedent(modifiers), '        ')}\n"
        "    }\n"
        "}\n"
    )


SELECT = ".chartXSelection(value: $picked)"


class SeriesTests(ScanTestCase):
    def test_two_plots_without_series(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .opacity(0.2)
            .accessibilityHidden(true)
        LinePlot(days, x: .value("Day", \\.date), y: .value("Steps", \\.steps))
        """
        self.assertRules(view(chart), ["CHART001"])

    def test_two_mark_lines_in_one_series(self) -> None:
        chart = """
        ForEach(days) { day in
            LineMark(x: .value("Date", day.date), y: .value("Steps", day.steps), series: .value("L", "Same"))
                .accessibilityHidden(true)
        }
        ForEach(days) { item in
            LineMark(x: .value("Date", item.date), y: .value("Steps", item.steps), series: .value("L", "Same"))
        }
        """
        self.assertRules(view(chart), ["CHART001"])

    def test_distinct_series(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps), series: .value("Layer", "Dimmed"))
            .accessibilityHidden(true)
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps), series: .value("Layer", "Active"))
        """
        self.assertRules(view(chart), [])

    def test_foreground_style_by_value_separates_series(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .foregroundStyle(by: .value("Layer", "Dimmed"))
            .accessibilityHidden(true)
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .foregroundStyle(by: .value("Layer", "Active"))
        """
        self.assertRules(view(chart), [])

    def test_plots_of_different_data_without_series(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        LinePlot(goal, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        """
        self.assertRules(view(chart, extra="let goal: [Day]"), ["CHART010"])

    def test_filtered_halves_without_series(self) -> None:
        chart = """
        LinePlot(days.filter { $0.steps > 0 }, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        LinePlot(days.filter { $0.steps <= 0 }, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .lineStyle(StrokeStyle(lineWidth: 2, dash: [4, 4]))
        """
        self.assertRules(view(chart), ["CHART010"])

    def test_plots_of_different_data_with_series(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps), series: .value("Line", "Steps"))
        LinePlot(goal, x: .value("Date", \\.date), y: .value("Steps", \\.steps), series: .value("Line", "Goal"))
        """
        self.assertRules(view(chart, extra="let goal: [Day]"), [])

    def test_copy_in_a_comment_is_ignored(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        // LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        /* LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps)) */
        """
        self.assertRules(view(chart), [])


class SlicingTests(ScanTestCase):
    def test_filter_by_selection(self) -> None:
        chart = """
        LinePlot(days.filter { $0.date <= (picked ?? .distantFuture) }, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        """
        self.assertRules(view(chart, SELECT), ["CHART002"])

    def test_prefix_while_by_selection(self) -> None:
        extra = 'var visible: [Day] { Array(days.prefix(while: { $0.date <= picked ?? .now })) }'
        chart = 'LinePlot(visible, x: .value("Date", \\.date), y: .value("Steps", \\.steps))'
        self.assertRules(view(chart, SELECT, extra), ["CHART002"])

    def test_filter_unrelated_to_selection(self) -> None:
        chart = 'LinePlot(days.filter { $0.steps > 0 }, x: .value("Date", \\.date), y: .value("Steps", \\.steps))'
        self.assertRules(view(chart, SELECT), [])


class MaskTests(ScanTestCase):
    def test_mask_from_first_point(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .mask {
                if let begin = days.first?.date {
                    RectangleMark(xStart: .value("Start", begin), xEnd: .value("End", domain.upperBound))
                }
            }
        """
        extra = "let domain: ClosedRange<Date>"
        self.assertRules(view(chart, extra=extra), ["CHART003"])

    def test_mask_falling_back_to_last_point(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .mask { RectangleMark(xStart: .value("Start", domain.lowerBound), xEnd: .value("End", selected?.date ?? days.last!.date)) }
        """
        extra = "let domain: ClosedRange<Date>\nvar selected: Day? { nil }"
        self.assertRules(view(chart, extra=extra), ["CHART003"])

    def test_mask_on_domain_bounds(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .mask { RectangleMark(xStart: .value("Start", domain.lowerBound), xEnd: .value("End", selected?.date ?? domain.upperBound)) }
        """
        extra = "let domain: ClosedRange<Date>\nvar selected: Day? { nil }"
        self.assertRules(view(chart, extra=extra), [])

    def test_rectangle_plot_with_constant_bounds(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .mask { RectanglePlot(days, xStart: .value("Start", domain.lowerBound), xEnd: .value("End", domain.upperBound)) }
        """
        self.assertRules(view(chart, extra="let domain: ClosedRange<Date>"), ["CHART004"])

    def test_rectangle_plot_with_key_paths(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .mask { RectanglePlot(bands, xStart: .value("Start", \\.start), xEnd: .value("End", \\.end)) }
        """
        self.assertRules(view(chart, extra="let bands: [Band]"), [])


class SelectionTests(ScanTestCase):
    def test_raw_selection_drives_a_rule(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        if let picked {
            RuleMark(x: .value("Picked", picked))
        }
        """
        self.assertRules(view(chart, SELECT), ["CHART005"])

    def test_clamped_selection(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        if let picked {
            RuleMark(x: .value("Picked", picked))
        }
        """
        modifiers = SELECT + """
        .onChange(of: picked) { _, value in
            guard let value else { return }
            picked = min(max(value, range.lowerBound), range.upperBound)
        }
        """
        self.assertRules(view(chart, modifiers, "let range: ClosedRange<Date>"), [])

    def test_snapped_selection(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        if let selected {
            RuleMark(x: .value("Picked", selected.date))
        }
        """
        self.assertRules(view(chart, SELECT, "var selected: Day? { nil }"), [])

    def test_annotation_formats_raw_selection(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        if let selected {
            RuleMark(x: .value("Picked", selected.date))
                .annotation(position: .top) {
                    Text(picked ?? .now, format: .dateTime.weekday())
                    Text(picked!, format: .dateTime.weekday())
                }
        }
        """
        self.assertRules(view(chart, SELECT, "var selected: Day? { nil }"), ["CHART008"])

    def test_annotation_formats_the_matched_element(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        if let selected {
            RuleMark(x: .value("Picked", selected.date))
                .annotation(position: .top) {
                    Text(selected.date, format: .dateTime.weekday())
                    Text("\\(selected.steps) steps")
                }
        }
        """
        self.assertRules(view(chart, SELECT, "var selected: Day? { nil }"), [])

    def test_hand_rolled_gesture(self) -> None:
        chart = 'LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))'
        modifiers = """
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle().fill(.clear).contentShape(Rectangle())
                    .gesture(DragGesture().onChanged { drag in
                        picked = proxy.value(atX: drag.location.x, as: Date.self)
                    })
            }
        }
        """
        self.assertRules(view(chart, modifiers), ["CHART009"])

    def test_built_in_selection(self) -> None:
        chart = 'LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))'
        self.assertRules(view(chart, SELECT), [])


class LayerTests(ScanTestCase):
    def test_area_and_line_with_different_interpolation(self) -> None:
        chart = """
        AreaPlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .interpolationMethod(.catmullRom)
            .accessibilityHidden(true)
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        """
        self.assertRules(view(chart), ["CHART007"])

    def test_area_and_line_with_the_same_interpolation(self) -> None:
        chart = """
        AreaPlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .interpolationMethod(.catmullRom)
            .accessibilityHidden(true)
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
            .interpolationMethod(.catmullRom)
        """
        self.assertRules(view(chart), [])

    def test_two_readable_copies(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps), series: .value("Layer", "Dimmed"))
            .opacity(0.2)
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps), series: .value("Layer", "Active"))
        """
        self.assertRules(view(chart), ["CHART006"])


class ProjectTests(ScanTestCase):
    def test_deployment_targets(self) -> None:
        self.write("App.xcodeproj/project.pbxproj", "IPHONEOS_DEPLOYMENT_TARGET = 17.0;\nIPHONEOS_DEPLOYMENT_TARGET = 18.2;\n")
        self.write("Package.swift", 'platforms: [.iOS(.v16), .macOS(.v14)]')
        targets = charts_scan.scan(self.root)["project"]["ios_deployment_targets"]
        self.assertEqual(targets, ["16.0", "17.0", "18.2"])

    def test_dependencies_are_skipped(self) -> None:
        chart = """
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))
        """
        self.write("Pods/Vendor/Chart.swift", HEADER + view(chart))
        self.assertEqual(charts_scan.scan(self.root)["findings"], [])
        self.assertTrue(charts_scan.scan(self.root, include_dependencies=True)["findings"])

    def test_scan_does_not_modify_files(self) -> None:
        path = self.write("Sources/Chart.swift", HEADER + view('LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))'))
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        with redirect_stdout(io.StringIO()):
            charts_scan.main([str(self.root), "--format", "markdown"])
            charts_scan.main([str(self.root), "--format", "json"])
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_inventory(self) -> None:
        self.write("Sources/Chart.swift", HEADER + view('LinePlot(days, x: .value("Date", \\.date), y: .value("Steps", \\.steps))', SELECT))
        inventory = charts_scan.scan(self.root)["inventory"]
        self.assertEqual(inventory["Chart"], 1)
        self.assertEqual(inventory["LinePlot"], 1)
        self.assertEqual(inventory["chartXSelection"], 1)


class OwnAdviceTests(ScanTestCase):
    """The skill's own recommended code must scan clean."""

    def test_reference_samples_have_no_findings_above_info(self) -> None:
        text = (SKILL / "references" / "masking-code.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```swift\n(.*?)```", text, re.S)
        self.assertGreaterEqual(len(blocks), 5)
        for index, block in enumerate(blocks, start=1):
            with self.subTest(block=index):
                self.write(f"Sample{index}/Sample.swift", block)
        findings = [f for f in charts_scan.scan(self.root)["findings"] if f["severity"] != "info"]
        self.assertEqual(findings, [])


class RuleMetadataTests(unittest.TestCase):
    def test_every_rule_cites_a_source(self) -> None:
        pattern = re.compile(
            r"WWDC2\d \d{5} .+ \d+:\d\d"
            r"|Apple documentation › "
            r"|Measured: scripts/probes/masking_probe\.swift"
        )
        for rule in charts_scan.RULES.values():
            with self.subTest(rule.id):
                self.assertRegex(rule.source, pattern)
                self.assertIn(rule.severity, charts_scan.SEVERITIES)

    def test_every_rule_is_listed_in_checks(self) -> None:
        checks = (ROOT / "CHECKS.md").read_text(encoding="utf-8")
        for rule_id in charts_scan.RULES:
            with self.subTest(rule_id):
                self.assertIn(rule_id, checks)


if __name__ == "__main__":
    unittest.main()
