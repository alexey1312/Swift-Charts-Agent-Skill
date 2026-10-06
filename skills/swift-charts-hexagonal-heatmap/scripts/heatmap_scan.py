#!/usr/bin/env python3
"""Read-only Swift Charts scanner for hexagonal heatmaps.

The scanner never modifies files. It finds the charts that draw hexagonal cells --
a `ChartSymbolShape` hexagon on point marks or plots, or hexagons built from area
marks -- and reports the patterns that draw them wrong: hexagons sized by one area,
automatic domains, cells drawn past the plot, binning while rendering, axial
coordinates rounded on their own, a linear color scale over counts, a hidden color
legend, area cells without a series, and an aspect ratio on the whole chart. It also
reports an inventory and the project's deployment targets, so an agent can reason
over structured JSON instead of ad hoc grep output.

Every rule cites where it comes from: an Apple session and timestamp, an Apple
documentation page, or the repository's own measurement (`hexagon_probe.swift`).
Matches are heuristics: read the surrounding code before recommending a change.

The parsing helpers are the same code as the dynamic masking skill's
`charts_scan.py`; `tests/test_heatmap_scan.py` keeps the two in step.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "1.1.0"

SEVERITIES = ["critical", "high", "medium", "low", "info"]

EXCLUDED_DIRS = {
    ".git",
    ".build",
    ".swiftpm",
    ".derived-data",
    "DerivedData",
    "build",
    "node_modules",
    "xcuserdata",
}

DEPENDENCY_DIRS = {"Pods", "Carthage", "checkouts", "SourcePackages", "vendor", "Vendor"}
CHART_OPEN = re.compile(r"\bChart\s*(?=[({])")


S_RAISE = "WWDC22 10137 Swift Charts: Raise the bar"
S_PLOTS = "WWDC24 10155 Swift Charts: Vectorized and function plots"
S_DESIGN = "WWDC22 110340 Design an effective chart"
D_PLOT_STYLE = "Apple documentation › chartPlotStyle(content:)"
PROBE = "Measured: scripts/probes/hexagon_probe.swift"


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    source: str
    advice: str


RULES: dict[str, Rule] = {
    rule.id: rule
    for rule in [
        Rule(
            id="HEX001",
            title="Hexagon sized by one area",
            severity="medium",
            source=PROBE + " §1–3",
            advice=(
                "`symbolSize(_ area:)` and `symbolSize(by:)` give one number. With the narrow "
                "`perceptualUnitRect` it sets the hexagon's height (the hexagon is sqrt(area) "
                "tall), so an area from the cell's width -- (width)² x 0.92 -- leaves 29 % of the "
                "plot as gap, and on a plot whose ratio is off the rows overlap. Size each "
                "hexagon with `symbolSize(CGSize(width:height:))`: sqrt(3) x radius times the x "
                "scale, 2 x radius times the y scale, read from the plot's size."
            ),
        ),
        Rule(
            id="HEX002",
            title="Hexagon chart without explicit x and y domains",
            severity="high",
            source=f"{PROBE} §4; {S_RAISE} 13:41",
            advice=(
                "The automatic numeric domain includes zero: points at longitude 166-179 and "
                "latitude -47 to -34 got x 0...200 and y -60...0, so the map filled 6 % of the "
                "plot's width. Give both axes an explicit domain with `chartXScale(domain:range:)` "
                "and `chartYScale(domain:range:)`, and compute the hexagon size and the plot's "
                "ratio from those domains."
            ),
        ),
        Rule(
            id="HEX003",
            title="Hexagon cells not clipped to the plot",
            severity="low",
            source=PROBE + " §5",
            advice=(
                "An explicit domain does not clip marks: a cell past the domain, and the outer "
                "half of a cell on its edge, draw over the axis labels. Add "
                "`.chartPlotStyle { $0.clipped() }` (with the plot's other modifiers)."
            ),
        ),
        Rule(
            id="HEX004",
            title="Observations binned while rendering",
            severity="medium",
            source=f"{S_PLOTS} 12:02, 12:14",
            advice=(
                "Grouping observations into cells inside `body`, or in a computed property a "
                "view reads, repeats the whole binning on every render. Bin once when the data "
                "changes -- in the model, in `init`, or in `.task` -- and keep the cells as "
                "stored properties."
            ),
        ),
        Rule(
            id="HEX005",
            title="Axial coordinates rounded independently",
            severity="medium",
            source=PROBE + " §6",
            advice=(
                "Rounding q and r on their own put 16.8 % of a million points in a neighboring "
                "cell. Round q, r and s = -q - r, then rebuild the coordinate that moved most so "
                "the three still add up to zero (cube rounding)."
            ),
        ),
        Rule(
            id="HEX006",
            title="Linear color scale over counts",
            severity="low",
            source=PROBE + " §7",
            advice=(
                "On a linear scale from 0 to 10,000, every count up to 100 got the first color "
                "of the ramp. When counts are skewed, use `type: .symmetricLog(slopeAtZero:)` "
                "(iOS 16.4): a count lands at log(1 + count x s) / log(1 + max x s). Check the "
                "distribution first; a linear scale is right for counts that spread evenly."
            ),
        ),
        Rule(
            id="HEX007",
            title="Color legend hidden",
            severity="low",
            source=f"{PROBE} §8; {S_DESIGN} 20:08",
            advice=(
                "For a continuous color scale the default legend is the color bar with its "
                "values -- the only key to what a color means. Keep it, or replace it with a "
                "key of your own; color should not be the only way a chart conveys critical "
                "information."
            ),
        ),
        Rule(
            id="HEX008",
            title="Area hexagons without a series per cell",
            severity="high",
            source=PROBE + " §10",
            advice=(
                "Area marks without a `series:` are grouped by their `foregroundStyle(by:)` "
                "value, so cells with the same count are joined into one area. Give every cell "
                'its own series, e.g. `series: .value("Cell", "\\(cell.q),\\(cell.r)")`.'
            ),
        ),
        Rule(
            id="HEX009",
            title="Aspect ratio on the whole chart while axes take space",
            severity="low",
            source=f"{PROBE} §3; {S_RAISE} 18:27; {D_PLOT_STYLE}",
            advice=(
                "With axes shown, `.aspectRatio` on the chart left the plot 1.5 % off the "
                "domains' ratio. Put the ratio on the plot: "
                "`.chartPlotStyle { $0.aspectRatio(ratio, contentMode: .fit) }`."
            ),
        ),
    ]
}

INVENTORY_PATTERNS = {
    "Chart": r"\bChart\s*[({]",
    "ChartSymbolShape": r"\bChartSymbolShape\b",
    "PointPlot": r"\bPointPlot\s*\(",
    "PointMark": r"\bPointMark\s*\(",
    "AreaMark": r"\bAreaMark\s*\(",
    "LinePlot": r"\bLinePlot\s*\(",
    "symbol": r"\.\s*symbol\s*\(",
    "symbolSize": r"\.\s*symbolSize\s*\(",
    "chartSymbolSizeScale": r"\bchartSymbolSizeScale\s*\(",
    "chartForegroundStyleScale": r"\bchartForegroundStyleScale\s*\(",
    "symmetricLog": r"\bsymmetricLog\b",
    "chartPlotStyle": r"\bchartPlotStyle\s*[({]",
    "onGeometryChange": r"\bonGeometryChange\s*\(",
    "chartXScale": r"\bchartXScale\s*\(",
    "chartYScale": r"\bchartYScale\s*\(",
    "chartLegend": r"\bchartLegend\s*\(",
    "Dictionary(grouping:)": r"\bDictionary\s*\(\s*grouping\s*:",
}

@dataclass
class Finding:
    id: str
    rule: str
    title: str
    severity: str
    file: str
    line: int
    snippet: str
    source: str
    advice: str


@dataclass
class Call:
    """One mark call inside a chart: `LinePlot(args).modifier(...)...`."""

    kind: str
    start: int
    args: dict[str, str]
    positional: list[str]
    modifiers: list[tuple[str, str]] = field(default_factory=list)

    def modifier(self, name: str) -> str | None:
        for modifier, argument in self.modifiers:
            if modifier == name:
                return argument
        return None


def strip_comments(text: str) -> str:
    """Blank out comments while keeping string literals and line numbers intact."""
    out: list[str] = []
    i, n = 0, len(text)
    depth = 0
    in_string = False
    multiline = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if depth:
            if ch == "*" and nxt == "/":
                depth -= 1
                out.append("  ")
                i += 2
            elif ch == "/" and nxt == "*":
                depth += 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_string:
            if ch == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue
            if multiline and text.startswith('"""', i):
                in_string = multiline = False
                out.append('"""')
                i += 3
                continue
            if not multiline and ch in '"\n':
                in_string = False
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            end = text.find("\n", i)
            end = n if end == -1 else end
            out.append(" " * (end - i))
            i = end
            continue
        if ch == "/" and nxt == "*":
            depth = 1
            out.append("  ")
            i += 2
            continue
        if text.startswith('"""', i):
            in_string = multiline = True
            out.append('"""')
            i += 3
            continue
        if ch == '"':
            in_string = True
        out.append(ch)
        i += 1
    return "".join(out)


def blank_strings(code: str) -> str:
    """Replace string literal contents with spaces so brackets inside them don't count.

    Offsets and line numbers stay the same. Interpolations are blanked with the rest
    of the literal, which is what bracket matching wants.
    """
    out = list(code)
    i, n = 0, len(code)
    while i < n:
        if code.startswith('"""', i):
            end = code.find('"""', i + 3)
            end = n if end == -1 else end
            for k in range(i + 3, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end + 3
            continue
        if code[i] == '"':
            k = i + 1
            depth = 0
            while k < n and code[k] != "\n":
                if code[k] == "\\" and k + 1 < n:
                    if code[k + 1] == "(":
                        depth += 1
                    out[k] = out[k + 1] = " "
                    k += 2
                    continue
                if depth and code[k] == ")":
                    depth -= 1
                elif not depth and code[k] == '"':
                    break
                out[k] = " "
                k += 1
            i = k + 1
            continue
        i += 1
    return "".join(out)


def matching(code: str, open_index: int) -> int:
    """Index of the bracket closing the one at `open_index`, or -1."""
    pairs = {"(": ")", "{": "}", "[": "]"}
    opener = code[open_index]
    closer = pairs[opener]
    depth = 0
    for index in range(open_index, len(code)):
        ch = code[index]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_arguments(text: str, blanked: str) -> list[str]:
    """Split a call's argument text at top-level commas."""
    parts: list[str] = []
    depth = 0
    start = 0
    for index, ch in enumerate(blanked):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def parse_call(code: str, blanked: str, name_start: int, kind: str) -> tuple[Call, int] | None:
    open_index = blanked.index("(", name_start)
    close_index = matching(blanked, open_index)
    if close_index == -1:
        return None
    inner = code[open_index + 1 : close_index]
    args: dict[str, str] = {}
    positional: list[str] = []
    for part in split_arguments(inner, blanked[open_index + 1 : close_index]):
        label = re.match(r"^(\w+)\s*:(?!:)\s*(.*)$", part, re.S)
        if label:
            args[label.group(1)] = label.group(2).strip()
        else:
            positional.append(part)
    call = Call(kind=kind, start=name_start, args=args, positional=positional)
    position = close_index + 1
    # Consume the modifier chain: `.name`, `.name(...)`, `.name { ... }`, `.name(...) { ... }`.
    chain = re.compile(r"\s*\.\s*(\w+)")
    while True:
        match = chain.match(blanked, position)
        if not match:
            break
        name = match.group(1)
        position = match.end()
        argument = ""
        while True:
            gap = re.match(r"[ \t]*", blanked[position:])
            probe = position + gap.end()
            if probe < len(blanked) and blanked[probe] in "({":
                end = matching(blanked, probe)
                if end == -1:
                    break
                argument += code[probe : end + 1]
                position = end + 1
                continue
            break
        call.modifiers.append((name, argument))
    return call, position


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def chart_blocks(code: str, blanked: str) -> list[tuple[int, int]]:
    """Content ranges of `Chart { ... }` and `Chart(data) { ... }`."""
    blocks: list[tuple[int, int]] = []
    for match in CHART_OPEN.finditer(blanked):
        position = match.end()
        if blanked[position] == "(":
            end = matching(blanked, position)
            if end == -1:
                continue
            position = end + 1
        brace = re.match(r"\s*\{", blanked[position:])
        if not brace:
            continue
        open_index = position + brace.end() - 1
        close_index = matching(blanked, open_index)
        if close_index != -1:
            blocks.append((open_index + 1, close_index))
    return blocks


def deployment_targets(root: Path, files: list[Path]) -> list[str]:
    targets: set[str] = set()
    for path in files:
        if path.suffix in {".pbxproj", ".xcconfig"}:
            text = read_text(path) or ""
            targets.update(re.findall(r"IPHONEOS_DEPLOYMENT_TARGET\s*=\s*\"?([\d.]+)", text))
        elif path.name == "Package.swift":
            text = read_text(path) or ""
            for major in re.findall(r"\.iOS\s*\(\s*\.v(\d+)", text):
                targets.add(f"{major}.0")
            targets.update(re.findall(r"\.iOS\s*\(\s*\"([\d.]+)\"", text))
    return sorted(targets, key=lambda value: [int(part) for part in value.split(".") if part.isdigit()])


def iter_project_files(root: Path, include_dependencies: bool) -> list[Path]:
    excluded = set(EXCLUDED_DIRS)
    if not include_dependencies:
        excluded |= DEPENDENCY_DIRS
    files: list[Path] = []
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name in excluded or entry.name.startswith("."):
                    continue
                if entry.suffix == ".xcodeproj":
                    pbxproj = entry / "project.pbxproj"
                    if pbxproj.is_file():
                        files.append(pbxproj)
                    continue
                stack.append(entry)
            elif entry.is_file() and (entry.suffix in {".swift", ".xcconfig"}):
                files.append(entry)
    return sorted(files)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def make_finding(rule_id: str, rel: str, text: str, index: int, severity: str | None = None) -> Finding:
    rule = RULES[rule_id]
    number = line_of(text, index)
    lines = text.splitlines()
    snippet = lines[number - 1] if number - 1 < len(lines) else ""
    return Finding(
        id=f"{rule.id}:{rel}:{number}",
        rule=rule.id,
        title=rule.title,
        severity=severity or rule.severity,
        file=rel,
        line=number,
        snippet=snippet.strip()[:200],
        source=rule.source,
        advice=rule.advice,
    )



SHAPE_DECLARATION = re.compile(r"\b(?:struct|class|enum|extension)\s+(\w+)\s*:\s*[^{]*\bChartSymbolShape\b[^{]*\{")
CONTENT_DECLARATION = re.compile(r"\bstruct\s+(\w+)\s*:\s*[^{]*\bChartContent\b[^{]*\{")
FUNCTION = re.compile(r"\bfunc\s+(\w+)\s*(?:<[^>]*>)?\s*\(")
CGSIZE_PROPERTY = re.compile(r"\b(?:let|var)\s+(\w+)\s*(?::\s*CGSize\b|=\s*CGSize\s*\()")
VIEW_STRUCT = re.compile(r"\bstruct\s+(\w+)\s*:\s*([^{]*)\{")
COMPUTED_PROPERTY = re.compile(r"\b(?:private\s+|fileprivate\s+)?var\s+(\w+)\s*:\s*[^={\n]+\{")
DEFERRED_CLOSURE = re.compile(r"\.\s*(?:task|onAppear|onChange|refreshable|onReceive)\b[^{]*\{|\bTask\s*(?:\([^)]*\))?\s*\{")
ROUNDING = re.compile(r"\.\s*rounded\s*\(|\b(?:l?round)\s*\(")
SQRT3 = re.compile(r"\bsqrt\s*\(\s*3(?:\.0)?\s*\)|\b3(?:\.0)?\s*\.\s*squareRoot\s*\(\s*\)")


def closure(blanked: str, open_index: int) -> tuple[int, int] | None:
    """Content range of the brace block that opens at `open_index`."""
    close_index = matching(blanked, open_index)
    return (open_index + 1, close_index) if close_index != -1 else None


def function_bodies(code: str, blanked: str) -> list[tuple[str, int, int, str]]:
    """(name, body start, body end, signature) for every `func` with a body."""
    found: list[tuple[str, int, int, str]] = []
    for match in FUNCTION.finditer(blanked):
        open_paren = match.end() - 1
        close_paren = matching(blanked, open_paren)
        if close_paren == -1:
            continue
        brace = re.match(r"[^{};]*\{", blanked[close_paren:])
        if not brace:
            continue
        body = closure(blanked, close_paren + brace.end() - 1)
        if body:
            found.append((match.group(1), body[0], body[1], code[match.start() : close_paren + brace.end()]))
    return found


@dataclass
class Project:
    """Facts gathered from every file before any chart is judged."""

    hexagon_shapes: set[str] = field(default_factory=set)
    # `ChartContent` types whose body draws a hexagon symbol.
    hexagon_contents: set[str] = field(default_factory=set)
    size_functions: set[str] = field(default_factory=set)
    size_properties: set[str] = field(default_factory=set)
    binning_functions: set[str] = field(default_factory=set)


def is_hexagon_shape(name: str, body: str) -> bool:
    if "hex" in name.lower():
        return True
    return body.count("CGPoint(") == 6 or (len(re.findall(r"\baddLine\s*\(", body)) == 5 and "move" in body)


def uses_hexagon(content: str, project: Project) -> bool:
    return any(
        re.search(r"\.\s*symbol\s*\(\s*" + re.escape(name) + r"\b", content) for name in project.hexagon_shapes
    ) or any(re.search(r"\b" + re.escape(name) + r"\s*\(", content) for name in project.hexagon_contents)


def hexagon_content_bodies(code: str, blanked: str, project: Project) -> list[tuple[int, int]]:
    """Body ranges of the `ChartContent` types in this file that draw hexagon symbols."""
    ranges: list[tuple[int, int]] = []
    for match in CONTENT_DECLARATION.finditer(blanked):
        if match.group(1) in project.hexagon_contents:
            body = closure(blanked, match.end() - 1)
            if body:
                ranges.append(body)
    return ranges


def gather(sources: list[tuple[str, str]]) -> Project:
    project = Project()
    parsed = [(strip_comments(text),) for _, text in sources]
    parsed = [(code, blank_strings(code)) for (code,) in parsed]
    for code, blanked in parsed:
        for match in SHAPE_DECLARATION.finditer(blanked):
            body = closure(blanked, match.end() - 1)
            if body and is_hexagon_shape(match.group(1), code[body[0] : body[1]]):
                project.hexagon_shapes.add(match.group(1))
    for code, blanked in parsed:
        for match in CONTENT_DECLARATION.finditer(blanked):
            body = closure(blanked, match.end() - 1)
            if body and uses_hexagon(code[body[0] : body[1]], project):
                project.hexagon_contents.add(match.group(1))
    for code, blanked in parsed:
        for name, start, end, signature in function_bodies(code, blanked):
            if re.search(r"->\s*CGSize\b", signature):
                project.size_functions.add(name)
            body = code[start:end]
            if re.search(r"\bDictionary\s*\(\s*grouping\s*:", body) or re.search(r"default\s*:\s*0\s*\]\s*\+=", body):
                project.binning_functions.add(name)
        project.size_properties.update(CGSIZE_PROPERTY.findall(code))
        for match in COMPUTED_PROPERTY.finditer(blanked):
            if re.search(r":\s*CGSize\s*\{", blanked[match.start() : match.end()]):
                project.size_properties.add(match.group(1))
    return project


def is_box_size(argument: str, project: Project) -> bool:
    """Is a `symbolSize(...)` argument a CGSize rather than an area?"""
    inner = argument.strip()[1:-1].strip() if argument.strip().startswith("(") else argument.strip()
    if inner.startswith("by:"):
        return False
    if "CGSize(" in inner:
        return True
    call = re.match(r"^(?:[\w.]+\.)?(\w+)\s*\(", inner)
    if call:
        return call.group(1) in project.size_functions
    name = re.match(r"^(?:self\.)?(\w+)$", inner)
    if name:
        return name.group(1) in project.size_properties
    return False


@dataclass
class HexChart:
    start: int
    content: tuple[int, int]
    chain: str
    symbols: bool
    areas: bool


def chain_after(code: str, blanked: str, position: int) -> str:
    """The modifier chain that follows a chart's closing brace, as source text."""
    end = position
    pattern = re.compile(r"\s*\.\s*\w+")
    while True:
        match = pattern.match(blanked, end)
        if not match:
            break
        end = match.end()
        while True:
            gap = re.match(r"[ \t]*", blanked[end:])
            probe = end + gap.end()
            if probe < len(blanked) and blanked[probe] in "({":
                close = matching(blanked, probe)
                if close == -1:
                    return code[position:end]
                end = close + 1
                continue
            break
    return code[position:end]


def nested_foreach_ranges(blanked: str, start: int, end: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in re.finditer(r"\bForEach\s*\(", blanked[start:end]):
        open_paren = start + match.end() - 1
        close_paren = matching(blanked, open_paren)
        if close_paren == -1:
            continue
        brace = re.match(r"\s*\{", blanked[close_paren + 1 :])
        if brace:
            body = closure(blanked, close_paren + 1 + brace.end() - 1)
            if body:
                ranges.append(body)
    return ranges


def area_calls(code: str, blanked: str, start: int, end: int) -> list[Call]:
    calls: list[Call] = []
    for match in re.finditer(r"\b(AreaMark|AreaPlot)\s*\(", blanked[start:end]):
        parsed = parse_call(code, blanked, start + match.start(), match.group(1))
        if parsed:
            calls.append(parsed[0])
    return calls


def hex_charts(code: str, blanked: str, project: Project) -> list[HexChart]:
    charts: list[HexChart] = []
    for start, end in chart_blocks(code, blanked):
        symbols = uses_hexagon(code[start:end], project)
        foreach = nested_foreach_ranges(blanked, start, end)
        areas = any(
            "yStart" in call.args and "yEnd" in call.args and sum(a <= call.start < b for a, b in foreach) >= 2
            for call in area_calls(code, blanked, start, end)
        )
        if symbols or areas:
            opener = blanked.rfind("Chart", 0, start)
            charts.append(HexChart(opener, (start, end), chain_after(code, blanked, end + 1), symbols, areas))
    return charts


def plot_style_closures(code: str, blanked: str) -> list[str]:
    bodies: list[str] = []
    for match in re.finditer(r"\bchartPlotStyle\s*(?:\(\s*content\s*:\s*)?\{", blanked):
        body = closure(blanked, match.end() - 1)
        if body:
            bodies.append(code[body[0] : body[1]])
    return bodies


def view_render_ranges(code: str, blanked: str) -> list[tuple[int, int]]:
    """`body` and computed properties of `View` structs: code that runs on every render."""
    ranges: list[tuple[int, int]] = []
    for match in VIEW_STRUCT.finditer(blanked):
        if not re.search(r"\bView\b", match.group(2)):
            continue
        struct_body = closure(blanked, match.end() - 1)
        if not struct_body:
            continue
        for prop in COMPUTED_PROPERTY.finditer(blanked, struct_body[0], struct_body[1]):
            body = closure(blanked, prop.end() - 1)
            if not body or re.match(r"\s*(?:didSet|willSet)\b", blanked[body[0] : body[1]]):
                continue
            ranges.append(body)
    return ranges


def deferred_ranges(blanked: str, start: int, end: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in DEFERRED_CLOSURE.finditer(blanked, start, end):
        body = closure(blanked, match.end() - 1)
        if body:
            ranges.append(body)
    return ranges


def scan_source(rel: str, text: str, project: Project) -> tuple[list[Finding], dict[str, int]]:
    code = strip_comments(text)
    blanked = blank_strings(code)
    inventory = {name: len(re.findall(pattern, blanked)) for name, pattern in INVENTORY_PATTERNS.items()}
    findings: list[Finding] = []
    plot_styles = plot_style_closures(code, blanked)
    clipped = any(re.search(r"\.\s*(?:clipped|clipShape)\s*\(", body) for body in plot_styles)

    # HEX001: a hexagon symbol sized by one area -- in a chart or in a hexagon content type.
    sized = [chart.content for chart in hex_charts(code, blanked, project) if chart.symbols]
    for start, end in sized + hexagon_content_bodies(code, blanked, project):
        for match in re.finditer(r"\.\s*symbolSize\s*\(", blanked[start:end]):
            open_paren = start + match.end() - 1
            close_paren = matching(blanked, open_paren)
            if close_paren != -1 and not is_box_size(code[open_paren : close_paren + 1], project):
                findings.append(make_finding("HEX001", rel, text, start + match.start()))

    for chart in hex_charts(code, blanked, project):
        start, end = chart.content
        context = code

        # HEX002: an automatic x or y domain.
        if not (re.search(r"\bchartXScale\s*\(\s*domain\s*:", context) and re.search(r"\bchartYScale\s*\(\s*domain\s*:", context)):
            findings.append(make_finding("HEX002", rel, text, chart.start))

        # HEX003: cells past the domain draw over the axes.
        if not clipped:
            findings.append(make_finding("HEX003", rel, text, chart.start))

        # HEX006: a linear scale for the counts' colors.
        for match in re.finditer(r"\bchartForegroundStyleScale\s*\(", blanked):
            close_paren = matching(blanked, match.end() - 1)
            if close_paren == -1:
                continue
            arguments = code[match.end() : close_paren]
            continuous = re.search(r"\b(?:Gradient|LinearGradient)\b|\bramp\b|\bgradient\b", arguments, re.I)
            linear = re.search(r"\btype\s*:\s*\.linear\b", arguments) or "type:" not in arguments
            if "range:" in arguments and continuous and linear:
                findings.append(make_finding("HEX006", rel, text, match.start()))
                break

        # HEX007: the color legend hidden. The style may sit in a hexagon content type.
        if re.search(r"\bforegroundStyle\s*\(\s*by\s*:", code):
            hidden = re.search(r"\.\s*chartLegend\s*\(\s*\.hidden\s*\)", code)
            if hidden:
                findings.append(make_finding("HEX007", rel, text, hidden.start()))

        # HEX008: area hexagons without a series.
        if chart.areas:
            foreach = nested_foreach_ranges(blanked, start, end)
            for call in area_calls(code, blanked, start, end):
                nested = sum(a <= call.start < b for a, b in foreach) >= 2
                if nested and "yStart" in call.args and "yEnd" in call.args and "series" not in call.args:
                    findings.append(make_finding("HEX008", rel, text, call.start))

        # HEX009: the ratio locked on the whole chart while axes take space.
        if re.search(r"\.\s*aspectRatio\s*\(", chart.chain):
            axes_hidden = re.search(r"chartXAxis\s*\(\s*\.hidden", context) and re.search(r"chartYAxis\s*\(\s*\.hidden", context)
            plot_ratio = any(re.search(r"\.\s*aspectRatio\s*\(", body) for body in plot_styles)
            if not axes_hidden and not plot_ratio:
                offset = code.find(chart.chain, end)
                ratio = re.search(r"\.\s*aspectRatio\s*\(", chart.chain)
                findings.append(make_finding("HEX009", rel, text, offset + ratio.start() if offset != -1 else chart.start))

    # HEX004: binning in `body` or a computed property of a view.
    binning = [re.escape(name) for name in project.binning_functions]
    pattern = re.compile(
        r"\bDictionary\s*\(\s*grouping\s*:" + (r"|\b(?:" + "|".join(binning) + r")\s*\(" if binning else "")
    )
    for render_start, render_end in view_render_ranges(code, blanked):
        deferred = deferred_ranges(blanked, render_start, render_end)
        for match in pattern.finditer(blanked, render_start, render_end):
            if not any(a <= match.start() < b for a, b in deferred):
                findings.append(make_finding("HEX004", rel, text, match.start()))
                break

    # HEX005: axial coordinates rounded on their own.
    for name, body_start, body_end, signature in function_bodies(code, blanked):
        body = code[body_start:body_end]
        axial = SQRT3.search(body) or (re.search(r"\bq\s*:", signature) and re.search(r"\br\s*:", signature))
        roundings = list(ROUNDING.finditer(blanked, body_start, body_end))
        if axial and len(roundings) == 2:
            findings.append(make_finding("HEX005", rel, text, roundings[0].start()))

    unique: dict[str, Finding] = {}
    for finding in findings:
        unique.setdefault(finding.id, finding)
    return list(unique.values()), inventory


def scan(root: Path, include_dependencies: bool = False) -> dict:
    root = root.resolve()
    files = iter_project_files(root, include_dependencies)
    sources: list[tuple[str, str]] = []
    for path in files:
        if path.suffix != ".swift":
            continue
        text = read_text(path)
        if text is not None:
            sources.append((relative(path, root), text))
    project = gather(sources)

    findings: list[Finding] = []
    inventory = {name: 0 for name in INVENTORY_PATTERNS}
    chart_files: list[str] = []
    hexagon_files: list[str] = []
    for rel, text in sources:
        file_findings, counts = scan_source(rel, text, project)
        findings.extend(file_findings)
        for name, count in counts.items():
            inventory[name] += count
        if counts["Chart"]:
            chart_files.append(rel)
            code = strip_comments(text)
            if hex_charts(code, blank_strings(code), project):
                hexagon_files.append(rel)

    findings.sort(key=lambda f: (SEVERITIES.index(f.severity), f.rule, f.file, f.line))
    by_severity = {severity: 0 for severity in SEVERITIES}
    by_rule: dict[str, int] = {}
    for finding in findings:
        by_severity[finding.severity] += 1
        by_rule[finding.rule] = by_rule.get(finding.rule, 0) + 1

    return {
        "tool": "heatmap_scan",
        "version": VERSION,
        "root": str(root),
        "read_only": True,
        "source_files_scanned": len(sources),
        "dependencies_included": include_dependencies,
        "project": {
            "ios_deployment_targets": deployment_targets(root, files),
            "files_with_charts": chart_files,
            "files_with_hexagon_charts": hexagon_files,
            "hexagon_shapes": sorted(project.hexagon_shapes),
        },
        "summary": {"by_severity": by_severity, "by_rule": by_rule},
        "findings": [asdict(finding) for finding in findings],
        "inventory": {name: count for name, count in inventory.items() if count},
    }


def render_markdown(report: dict, limit: int) -> str:
    targets = ", ".join(report["project"]["ios_deployment_targets"]) or "not found"
    shapes = ", ".join(f"`{name}`" for name in report["project"]["hexagon_shapes"]) or "none"
    lines = [
        "# Swift Charts hexagonal heatmap scan",
        "",
        f"- Root: `{report['root']}`",
        f"- Swift files scanned: {report['source_files_scanned']}",
        f"- Files with charts: {len(report['project']['files_with_charts'])}",
        f"- Files with hexagon charts: {len(report['project']['files_with_hexagon_charts'])}",
        f"- Hexagon symbol shapes: {shapes}",
        f"- iOS deployment targets: {targets}",
        "- Read-only: nothing was modified. Matches are heuristics; read the code before acting.",
        "",
        "## Summary",
        "",
        "| Severity | Count |",
        "| --- | ---: |",
    ]
    for severity, count in report["summary"]["by_severity"].items():
        lines.append(f"| {severity} | {count} |")
    lines += ["", "## Findings", ""]
    findings = report["findings"]
    if not findings:
        lines.append("No findings.")
    for finding in findings[:limit]:
        lines.append(
            f"- **{finding['rule']} {finding['title']}** ({finding['severity']}) "
            f"`{finding['file']}:{finding['line']}`  \n  `{finding['snippet']}`"
        )
    if len(findings) > limit:
        lines.append(f"- … {len(findings) - limit} more (use --format json for all)")
    if report["inventory"]:
        lines += ["", "## Inventory", "", "| API | Occurrences |", "| --- | ---: |"]
        for name, count in report["inventory"].items():
            lines.append(f"| `{name}` | {count} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="Project or package root to scan")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--include-dependencies", action="store_true", help="Also scan Pods, Carthage, SwiftPM checkouts and vendor folders")
    parser.add_argument("--limit", type=int, default=200, help="Maximum findings listed in markdown output")
    parser.add_argument("--fail-on", choices=SEVERITIES, help="Exit with status 2 when a finding at or above this severity exists")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    report = scan(root, include_dependencies=args.include_dependencies)
    if args.format == "json":
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(report, args.limit))

    if args.fail_on:
        threshold = SEVERITIES.index(args.fail_on)
        if any(SEVERITIES.index(f["severity"]) <= threshold for f in report["findings"]):
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
