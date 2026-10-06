from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills" / "swift-charts-hexagonal-heatmap" / "scripts" / "heatmap_sdk_check.py"
MASKING = ROOT / "skills" / "swift-charts-dynamic-masking" / "scripts" / "charts_sdk_check.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


heatmap_sdk_check = load("heatmap_sdk_check", SCRIPT)
charts_sdk_check = load("charts_sdk_check_shared", MASKING)

# Shaped like the real Charts.swiftinterface: a point-release extension, and a protocol
# requirement whose availability comes from the protocol.
INTERFACE = """\
@available(iOS 16.0, macOS 13.0, tvOS 16.0, watchOS 9.0, *)
public struct ScaleType {
  public static var linear: Charts::ScaleType {
    get
  }
}
@available(iOS 16.4, macOS 13.3, tvOS 16.4, watchOS 9.4, *)
extension Charts::ScaleType {
  public static func symmetricLog(slopeAtZero: Swift::Double) -> Charts::ScaleType
}
@available(iOS 16.0, macOS 13.0, tvOS 16.0, watchOS 9.0, *)
public protocol ChartSymbolShape : SwiftUICore::Shape {
  var perceptualUnitRect: CoreFoundation::CGRect { get }
}
@available(iOS 16.0, macOS 13.0, tvOS 16.0, watchOS 9.0, *)
extension SwiftUICore::Gradient : Charts::ScaleRange {
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
        symbols = [symbol for symbol in heatmap_sdk_check.SYMBOLS if symbol.name == name]
        self.assertEqual(len(symbols), 1, name)
        return heatmap_sdk_check.check(self.interface, symbols)[0]

    def test_point_release_extension(self) -> None:
        self.assertEqual(self.row("ScaleType.symmetricLog(slopeAtZero:)")["ios"], "16.4")

    def test_protocol_requirement(self) -> None:
        row = self.row("ChartSymbolShape.perceptualUnitRect")
        self.assertTrue(row["found"])
        self.assertEqual(row["ios"], "16.0")

    def test_conformance_extension(self) -> None:
        self.assertEqual(self.row("Gradient as a ScaleRange")["ios"], "16.0")

    def test_missing_symbol(self) -> None:
        self.assertFalse(self.row("PointPlot")["found"])


class SharedCodeTests(unittest.TestCase):
    """Everything but SYMBOLS is the masking skill's charts_sdk_check.py."""

    def test_functions_match_the_masking_check(self) -> None:
        names = [
            name
            for name, value in vars(charts_sdk_check).items()
            if inspect.isfunction(value) and value.__module__ == charts_sdk_check.__name__
        ]
        self.assertIn("check", names)
        for name in names:
            with self.subTest(name):
                self.assertEqual(
                    inspect.getsource(getattr(heatmap_sdk_check, name)), inspect.getsource(getattr(charts_sdk_check, name))
                )
        self.assertEqual(inspect.getsource(heatmap_sdk_check.Symbol), inspect.getsource(charts_sdk_check.Symbol))
        for name in ("AVAILABLE", "QUALIFIER", "IOS_VERSION", "IOS_DEPRECATED", "DECLARATION"):
            with self.subTest(name):
                self.assertEqual(getattr(heatmap_sdk_check, name).pattern, getattr(charts_sdk_check, name).pattern)


@unittest.skipUnless(shutil.which("xcrun"), "needs Xcode")
class InstalledSDKTests(unittest.TestCase):
    def test_every_symbol_is_found_with_an_ios_version(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--platform", "iphonesimulator", "--format", "json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)["symbols"]
        for row in rows:
            with self.subTest(row["symbol"]):
                self.assertTrue(row["found"])
                self.assertTrue(row["ios"])
        floors = {row["symbol"]: row.get("ios") or "" for row in rows}
        # The versions the skill's text relies on.
        self.assertEqual(floors["ScaleType.symmetricLog(slopeAtZero:)"], "16.4")
        self.assertEqual(floors["ChartContent.symbolSize(_ size: CGSize)"].split(".")[0], "16")
        self.assertEqual(floors["ChartSymbolShape.perceptualUnitRect"].split(".")[0], "16")
        self.assertEqual(floors["AreaMark(x:yStart:yEnd:series:)"].split(".")[0], "16")
        self.assertEqual(floors["PointPlot(_:x:y:)"].split(".")[0], "18")


if __name__ == "__main__":
    unittest.main()
