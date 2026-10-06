#!/usr/bin/env python3
"""Report which Swift Charts heatmap APIs the selected SDK declares, and since when.

Blog posts and session samples are snapshots; the Swift interface the compiler
reads is the ground truth. This reads `Charts.swiftinterface` from the selected
SDK, finds each declaration the hexagonal heatmap skill teaches, and reports the
iOS version its `@available` attribute names -- the floor a deployment target must
meet without an `if #available` gate. Read-only: it only reads SDK files.

Everything except SYMBOLS is the same code as the dynamic masking skill's
`charts_sdk_check.py`; `tests/test_heatmap_sdk_check.py` keeps the two in step.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VERSION = "1.1.0"


@dataclass(frozen=True)
class Symbol:
    """A declaration to find. `pattern` matches its line in the Swift interface."""

    name: str
    pattern: str
    role: str
    note: str = ""
    # Text the enclosing type or extension line must contain, for initializers that
    # several marks declare with the same signature.
    within: str = ""


SYMBOLS: list[Symbol] = [
    # Cells.
    Symbol("PointPlot", r"public struct PointPlot<", "cells", "vectorized points for a whole collection"),
    Symbol("PointPlot(_:x:y:)", r"public init<Data>\(_ data: Data, x: PlottableProjection<PointPlot<Content>\.DataElement, some Plottable>, y: PlottableProjection", "cells"),
    Symbol("PointMark(x:y:)", r"public init<X, Y>\(x: PlottableValue<X>, y: PlottableValue<Y>\) where", "cells", "ForEach + PointMark draws the same pixels", within="struct PointMark"),
    Symbol("AreaMark(x:yStart:yEnd:series:)", r"public init<X, Y, S>\(x: PlottableValue<X>, yStart: PlottableValue<Y>, yEnd: PlottableValue<Y>, series:", "cells", "hexagons in data space, one series per cell", within="struct AreaMark"),
    Symbol("AreaPlot(_:x:yStart:yEnd:series:)", r"public init<Data, Y>\(_ data: Data, x: [^)]*yStart: [^)]*series:", "cells"),
    Symbol("LinePlot(_:x:y:series:)", r"public init<Data>\(_ data: Data, x: PlottableProjection<LinePlot<Content>\.DataElement, some Plottable>, y: [^)]*series:", "outline", "one series per outline segment"),
    # Symbol.
    Symbol("ChartSymbolShape", r"public protocol ChartSymbolShape\b", "symbol"),
    Symbol("ChartSymbolShape.perceptualUnitRect", r"var perceptualUnitRect: CGRect \{ get \}", "symbol", "a requirement with no default", within="protocol ChartSymbolShape"),
    Symbol("ChartContent.symbol(_:)", r"public func symbol<S>\(_ symbol: S\) -> some ChartContent where S : ChartSymbolShape", "symbol"),
    Symbol("ChartContent.symbolSize(_ area:)", r"public func symbolSize\(_ area: CGFloat\) -> some ChartContent", "symbol", "sets the height of a narrow-rect hexagon"),
    Symbol("ChartContent.symbolSize(_ size: CGSize)", r"public func symbolSize\(_ size: CGSize\) -> some ChartContent", "symbol", "exact width and height"),
    Symbol("VectorizedChartContent.symbolSize(by:)", r"public func symbolSize\(by value: PlottableProjection<Self\.DataElement", "symbol"),
    Symbol("View.chartSymbolSizeScale(domain:range:type:)", r"public func chartSymbolSizeScale<Domain, Range>\(domain:", "symbol"),
    # Color.
    Symbol("ChartContent.foregroundStyle(by:)", r"public func foregroundStyle<D>\(by value: PlottableValue<D>\) -> some ChartContent", "color"),
    Symbol("View.chartForegroundStyleScale(domain:range:type:)", r"public func chartForegroundStyleScale<Domain, Range>\(domain:", "color"),
    Symbol("Gradient as a ScaleRange", r"^extension Gradient : ScaleRange", "color", "a continuous color ramp"),
    Symbol("ScaleType.symmetricLog(slopeAtZero:)", r"public static func symmetricLog\(slopeAtZero:", "color", "iOS 16.4: gate it below that"),
    Symbol("View.chartLegend(_:)", r"public func chartLegend\(_ visibility: Visibility\)", "color", "keep the color bar"),
    # Plot and scales.
    Symbol("View.chartXScale(domain:range:type:)", r"public func chartXScale<Domain, Range>\(domain:", "scale", "an automatic domain includes zero"),
    Symbol("plotDimension(padding:)", r"public static func plotDimension\(padding:", "scale"),
    Symbol("View.chartPlotStyle(content:)", r"public func chartPlotStyle<Content>\(", "scale", "aspectRatio, clipped and the plot size"),
    # Accessibility.
    Symbol("ChartContent.accessibilityLabel(_:) string", r"public func accessibilityLabel<S>\(_ label: S\) -> some ChartContent", "accessibility"),
    Symbol("VectorizedChartContent.accessibilityLabel(_:) key path", r"public func accessibilityLabel\(_ label: KeyPath<Self\.DataElement, some StringProtocol>\)", "accessibility"),
    Symbol("ChartContent.accessibilityHidden(_:)", r"public func accessibilityHidden\(_ hidden: Bool\) -> some ChartContent", "accessibility", "for an outline"),
]

AVAILABLE = re.compile(r"@available\(([^)]*)\)")
# Module qualifiers differ between SDKs: the iOS 27 interfaces write `Swift::Bool` and
# `Charts::ChartContent`, the iOS 26 ones `Swift.Bool` and `Charts.ChartContent`.
# Patterns are written unqualified and matched against lines with both forms removed.
QUALIFIER = re.compile(
    r"\b(?:Swift|Charts|SwiftUI|SwiftUICore|CoreFoundation|CoreGraphics|Foundation|_Concurrency|Spatial)(?:::|\.)(?=[A-Za-z_])"
)


def unqualified(line: str) -> str:
    return QUALIFIER.sub("", line)
IOS_VERSION = re.compile(r"\biOS (\d+(?:\.\d+)*)")
IOS_DEPRECATED = re.compile(r"\biOS, (?:introduced: [\d.]+, )?deprecated(?:: ([\d.]+))?")


def run(command: list[str]) -> str | None:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def charts_interface(sdk: Path) -> Path | None:
    module = sdk / "System" / "Library" / "Frameworks" / "Charts.framework" / "Modules" / "Charts.swiftmodule"
    candidates = sorted(p for p in module.glob("*.swiftinterface") if "private" not in p.name and "macabi" not in p.name)
    preferred = [p for p in candidates if p.name.startswith("arm64")]
    chosen = preferred or candidates
    return chosen[0] if chosen else None


def attributes_above(lines: list[str], index: int) -> list[str]:
    """`@available` attributes on the lines directly above `index`."""
    found: list[str] = []
    cursor = index - 1
    while cursor >= 0 and lines[cursor].lstrip().startswith("@"):
        found.extend(AVAILABLE.findall(lines[cursor]))
        cursor -= 1
    found.extend(AVAILABLE.findall(lines[index].split("public", 1)[0]))
    return found


DECLARATION = re.compile(r"\b(?:struct|extension|class|enum|protocol|actor)\b")


def enclosing_declaration(lines: list[str], index: int) -> int | None:
    """The top-level `extension` or type whose body contains line `index`.

    Top-level lines in a Swift interface are unindented. A declaration line can begin
    with attributes (`@_Concurrency::MainActor @preconcurrency public struct LineMark {`),
    so a leading `@` alone does not make a line an attribute line.
    """
    if not lines[index].startswith((" ", "\t")):
        return None
    for cursor in range(index - 1, -1, -1):
        line = lines[cursor]
        if not line or line.startswith((" ", "\t", "}", "#")):
            continue
        if line.startswith("@") and not DECLARATION.search(line):
            continue
        return cursor
    return None


def availability(lines: list[str], index: int) -> dict:
    member = attributes_above(lines, index)
    parent_index = enclosing_declaration(lines, index)
    parent = attributes_above(lines, parent_index) if parent_index is not None else []
    introduced = None
    for attribute in member + parent:  # the member's own attribute is more specific
        match = IOS_VERSION.search(attribute)
        if match:
            introduced = match.group(1)
            break
    deprecated = None
    for attribute in member + parent:
        match = IOS_DEPRECATED.search(attribute)
        if match:
            deprecated = match.group(1) or "yes"
            break
    return {"ios": introduced, "ios_deprecated": deprecated, "attributes": member + parent}


def check(interface: Path, symbols: list[Symbol]) -> list[dict]:
    lines = [unqualified(line) for line in interface.read_text(encoding="utf-8", errors="replace").splitlines()]
    rows = []
    for symbol in symbols:
        pattern = re.compile(symbol.pattern)
        index = next(
            (
                i
                for i, line in enumerate(lines)
                if pattern.search(line)
                and (not symbol.within or symbol.within in lines[enclosing_declaration(lines, i) or 0])
            ),
            None,
        )
        row = {"symbol": symbol.name, "role": symbol.role, "note": symbol.note, "found": index is not None}
        if index is not None:
            row.update(availability(lines, index))
            row["line"] = index + 1
            row["declaration"] = lines[index].strip()[:240]
        rows.append(row)
    return rows


def render_markdown(report: dict) -> str:
    lines = [
        "# Swift Charts SDK check",
        "",
        f"- SDK: `{report['sdk_path']}` (version {report['sdk_version']})",
        f"- Xcode: {report['xcode_version']}",
        f"- Interface: `{report['interface']}`",
        "",
        "| API | Role | In SDK | iOS | Deprecated | Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["symbols"]:
        found = "yes" if row["found"] else "**no**"
        lines.append(
            f"| `{row['symbol']}` | {row['role']} | {found} | {row.get('ios') or ''} | "
            f"{row.get('ios_deprecated') or ''} | {row['note']} |"
        )
    missing = [row["symbol"] for row in report["symbols"] if not row["found"]]
    if missing:
        lines += [
            "",
            "Missing APIs do not compile with this SDK. Do not write code against them.",
        ]
    lines += [
        "",
        "Code that uses an API whose iOS version is above the deployment target needs "
        "`if #available(iOS <version>, *)` around it, or a fallback for older systems.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sdk", help="SDK path; defaults to `xcrun --sdk <platform> --show-sdk-path`")
    parser.add_argument("--platform", default="iphoneos", help="xcrun SDK name, default iphoneos")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args(argv)

    sdk_path = args.sdk or run(["xcrun", "--sdk", args.platform, "--show-sdk-path"])
    if not sdk_path or not Path(sdk_path).is_dir():
        parser.error("could not resolve an SDK; pass --sdk or select an Xcode with xcode-select")
    sdk = Path(sdk_path)
    interface = charts_interface(sdk)
    if interface is None:
        parser.error(f"no Charts.swiftinterface in {sdk}")

    report = {
        "tool": "charts_sdk_check",
        "version": VERSION,
        "sdk_path": str(sdk),
        "sdk_version": (run(["xcrun", "--sdk", args.platform, "--show-sdk-version"]) if not args.sdk else None) or "unknown",
        "xcode_version": (run(["xcodebuild", "-version"]) or "unknown").replace("\n", ", "),
        "interface": str(interface.relative_to(sdk)),
        "symbols": check(interface, SYMBOLS),
    }
    if args.format == "json":
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
