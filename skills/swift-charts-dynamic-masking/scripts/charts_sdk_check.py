#!/usr/bin/env python3
"""Report which Swift Charts selection and masking APIs the selected SDK declares, and since when.

Blog posts and session samples are snapshots; the Swift interface the compiler
reads is the ground truth. This reads `Charts.swiftinterface` from the selected
SDK, finds each declaration the skill teaches, and reports the iOS version its
`@available` attribute names -- the floor a deployment target must meet without
an `if #available` gate. Read-only: it only reads SDK files.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VERSION = "1.0.0"


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
    # Layers.
    Symbol("LinePlot", r"public struct LinePlot<", "layer", "vectorized line for a whole collection"),
    Symbol("LinePlot(_:x:y:series:)", r"public init<Data>\(_ data: Data, x: Charts::PlottableProjection<Charts::LinePlot<Content>\.DataElement, some Plottable>, y: [^)]*series:", "layer", "series keeps two copies of one line apart"),
    Symbol("AreaPlot", r"public struct AreaPlot<", "layer"),
    Symbol("LineMark", r"public struct LineMark\b", "layer"),
    Symbol("LineMark(x:y:series:)", r"public init<X, Y, S>\(x: Charts::PlottableValue<X>, y: Charts::PlottableValue<Y>, series: Charts::PlottableValue<S>\)", "layer", within="struct LineMark"),
    Symbol("AreaMark", r"public struct AreaMark\b", "layer"),
    Symbol("RuleMark", r"public struct RuleMark\b", "layer"),
    Symbol("PlottableProjection.value(_:_:) constant", r"public static func value\(_ label: some StringProtocol, _ value: DataValue\) -> Charts::PlottableProjection", "layer", "a constant in a plot argument, e.g. series: .value(\"Layer\", \"Dimmed\")"),
    # Masking.
    Symbol("ChartContent.mask(content:)", r"public func mask<C>\(", "mask"),
    Symbol("RectangleMark(xStart:xEnd:yStart:yEnd:)", r"public init<X>\(xStart: Charts::PlottableValue<X>, xEnd: Charts::PlottableValue<X>, yStart: CoreFoundation::CGFloat\? = nil", "mask", "one rectangle, full plot height", within="struct RectangleMark"),
    Symbol("RectanglePlot", r"public struct RectanglePlot<", "mask", "one rectangle per element"),
    Symbol("ChartContent.opacity(_:)", r"public func opacity\(_ value: Swift::Double\) -> some Charts::ChartContent", "layer"),
    Symbol("ChartContent.accessibilityHidden(_:)", r"public func accessibilityHidden\(_ hidden: Swift::Bool\) -> some Charts::ChartContent", "accessibility"),
    Symbol("ChartContent.interpolationMethod(_:)", r"public func interpolationMethod\(_ method: Charts::InterpolationMethod\)", "layer"),
    Symbol("ChartContent.alignsMarkStylesWithPlotArea(_:)", r"public func alignsMarkStylesWithPlotArea\(", "layer"),
    Symbol("ChartContent.zIndex(_:)", r"public func zIndex\(_ value: Swift::Double\) -> some Charts::ChartContent", "layer", "the talk keeps the selection rule behind the lines with a negative zIndex"),
    # Selection.
    Symbol("View.chartXSelection(value:)", r"public func chartXSelection<P>\(value:", "selection"),
    Symbol("View.chartXSelection(range:)", r"public func chartXSelection<P>\(range:", "selection", "two fingers on iOS, drag on macOS"),
    Symbol("View.chartGesture(_:)", r"public func chartGesture\(", "selection"),
    Symbol("ChartProxy.selectXValue(at:)", r"public func selectXValue\(at ", "selection"),
    Symbol("View.chartOverlay(alignment:content:)", r"public func chartOverlay<V>\(", "selection", "the iOS 16 route, with a DragGesture"),
    Symbol("ChartProxy.value(atX:as:)", r"public func value<P>\(atX position:", "selection"),
    Symbol("ChartProxy.plotFrame", r"public var plotFrame: ", "selection", "replaces plotAreaFrame"),
    Symbol("ChartProxy.plotAreaFrame", r"public var plotAreaFrame: ", "selection"),
    Symbol("annotation(...overflowResolution:)", r"public func annotation<C>\([^)]*overflowResolution:", "selection"),
    # Scale.
    Symbol("View.chartXScale(domain:range:type:)", r"public func chartXScale<Domain, Range>\(domain:", "scale"),
    Symbol("plotDimension(startPadding:endPadding:)", r"public static func plotDimension\(startPadding:", "scale", "padding in points, outside the domain"),
]

AVAILABLE = re.compile(r"@available\(([^)]*)\)")
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
    lines = interface.read_text(encoding="utf-8", errors="replace").splitlines()
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
