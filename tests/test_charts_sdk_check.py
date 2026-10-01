from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "swift-charts-dynamic-masking" / "scripts" / "charts_sdk_check.py"
SPEC = importlib.util.spec_from_file_location("charts_sdk_check", SCRIPT)
assert SPEC and SPEC.loader
charts_sdk_check = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = charts_sdk_check
SPEC.loader.exec_module(charts_sdk_check)

# Shaped like the real Charts.swiftinterface: the types' availability sits on the
# line above a declaration line that itself starts with attributes.
INTERFACE = """\
@available(iOS 18.0, macOS 15.0, tvOS 18.0, watchOS 11.0, visionOS 2.0, *)
@_Concurrency::MainActor @preconcurrency public struct VectorizedBarPlotContent<Data> {
  public typealias DataElement = Data.Element
}
@available(iOS 16.0, macOS 13.0, tvOS 16.0, watchOS 9.0, *)
@_Concurrency::MainActor @preconcurrency public struct LineMark {
  nonisolated public init<X, Y, S>(x: Charts::PlottableValue<X>, y: Charts::PlottableValue<Y>, series: Charts::PlottableValue<S>) where X : Charts::Plottable
}
@available(iOS 16.0, macOS 13.0, tvOS 16.0, watchOS 9.0, *)
public struct ChartProxy {
  @available(iOS, deprecated: 17.0, renamed: "plotFrame")
  public var plotAreaFrame: SwiftUICore::Anchor<CoreFoundation::CGRect> {
    get
  }
  @available(iOS 17.0, macOS 14.0, *)
  public var plotFrame: SwiftUICore::Anchor<CoreFoundation::CGRect>? {
    get
  }
}
@available(iOS 17, macOS 14, tvOS 17, watchOS 10, *)
extension Charts::ChartContent {
  nonisolated public func zIndex(_ value: Swift::Double) -> some Charts::ChartContent
}
"""


# The iOS 26 SDK's spelling of the same declarations: `.` instead of `::`, no `nonisolated`.
INTERFACE_26 = """\
@available(iOS 16.0, macOS 13.0, tvOS 16.0, watchOS 9.0, *)
@_Concurrency.MainActor @preconcurrency public struct LineMark {
  public init<X, Y, S>(x: Charts.PlottableValue<X>, y: Charts.PlottableValue<Y>, series: Charts.PlottableValue<S>) where X : Charts.Plottable
}
@available(iOS 16.0, macOS 13.0, tvOS 16.0, watchOS 9.0, *)
extension Charts.ChartContent {
  public func accessibilityHidden(_ hidden: Swift.Bool) -> some Charts.ChartContent
}
@available(iOS 16.0, macOS 13.0, tvOS 16.0, watchOS 9.0, *)
@_Concurrency.MainActor @preconcurrency public struct RectangleMark {
  public init<X>(xStart: Charts.PlottableValue<X>, xEnd: Charts.PlottableValue<X>, yStart: CoreFoundation.CGFloat? = nil, yEnd: CoreFoundation.CGFloat? = nil) where X : Charts.Plottable
}
"""


class AvailabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.interface = Path(self._directory.name) / "Charts.swiftinterface"
        self.interface.write_text(INTERFACE, encoding="utf-8")

    def tearDown(self) -> None:
        self._directory.cleanup()

    def row(self, name: str) -> dict:
        symbols = [symbol for symbol in charts_sdk_check.SYMBOLS if symbol.name == name]
        self.assertEqual(len(symbols), 1, name)
        return charts_sdk_check.check(self.interface, symbols)[0]

    def test_type_availability_through_an_attributed_declaration_line(self) -> None:
        # Regression: a declaration line starting with `@_Concurrency::MainActor` was
        # taken for an attribute, and the previous type's iOS 18 was reported.
        row = self.row("LineMark(x:y:series:)")
        self.assertTrue(row["found"])
        self.assertEqual(row["ios"], "16.0")

    def test_member_attribute_wins_over_the_type(self) -> None:
        row = self.row("ChartProxy.plotFrame")
        self.assertEqual(row["ios"], "17.0")
        deprecated = self.row("ChartProxy.plotAreaFrame")
        self.assertEqual(deprecated["ios"], "16.0")
        self.assertEqual(deprecated["ios_deprecated"], "17.0")

    def test_extension_availability_without_a_minor_version(self) -> None:
        self.assertEqual(self.row("ChartContent.zIndex(_:)")["ios"], "17")

    def test_missing_symbol(self) -> None:
        self.assertFalse(self.row("LinePlot")["found"])

    def test_dot_qualified_interface(self) -> None:
        self.interface.write_text(INTERFACE_26, encoding="utf-8")
        for name in ("LineMark(x:y:series:)", "ChartContent.accessibilityHidden(_:)", "RectangleMark(xStart:xEnd:yStart:yEnd:)"):
            with self.subTest(name):
                row = self.row(name)
                self.assertTrue(row["found"])
                self.assertEqual(row["ios"], "16.0")

    def test_within_restricts_to_the_named_type(self) -> None:
        symbol = charts_sdk_check.Symbol("other", r"public init<X, Y, S>\(x:", "layer", within="struct RuleMark")
        self.assertFalse(charts_sdk_check.check(self.interface, [symbol])[0]["found"])


@unittest.skipUnless(shutil.which("xcrun"), "needs Xcode")
class InstalledSDKTests(unittest.TestCase):
    def test_every_symbol_is_found_with_an_ios_version(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--platform", "iphonesimulator", "--format", "json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        import json

        rows = json.loads(result.stdout)["symbols"]
        for row in rows:
            with self.subTest(row["symbol"]):
                self.assertTrue(row["found"])
                self.assertTrue(row["ios"])
        floors = {row["symbol"]: (row.get("ios") or "").split(".")[0] for row in rows}
        # The versions the skill's text relies on.
        self.assertEqual(floors["ChartContent.mask(content:)"], "16")
        self.assertEqual(floors["LineMark(x:y:series:)"], "16")
        self.assertEqual(floors["RectangleMark(xStart:xEnd:yStart:yEnd:)"], "16")
        self.assertEqual(floors["View.chartXSelection(value:)"], "17")
        self.assertEqual(floors["LinePlot(_:x:y:series:)"], "18")


if __name__ == "__main__":
    unittest.main()
