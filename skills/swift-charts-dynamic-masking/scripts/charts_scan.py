#!/usr/bin/env python3
"""Read-only Swift Charts scanner for selection, layering and masking.

The scanner never modifies files. It finds the chart code a selection-driven
highlight touches -- `Chart` blocks, line and area marks, masks, selection
bindings -- and reports the patterns that draw something wrong: copies of a line
that Swift Charts joins into one, masks that clip the first and last points,
selections that leave the data, data sliced on every drag. It also reports an
inventory and the project's deployment targets, so an agent can reason over
structured JSON instead of ad hoc grep output.

Every rule cites where it comes from: an Apple session and timestamp, an Apple
documentation page, or the repository's own measurement (`masking_probe.swift`).
Matches are heuristics: read the surrounding code before recommending a change.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "1.0.0"

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

S_SELECT = "WWDC23 10037 Explore pie charts and interactivity in Swift Charts"
S_PLOTS = "WWDC24 10155 Swift Charts: Vectorized and function plots"
S_RAISE = "WWDC22 10137 Swift Charts: Raise the bar"
D_LINEMARK = "Apple documentation › LineMark (series)"
D_MASK = "Apple documentation › ChartContent.mask(content:)"
D_HIDDEN = "Apple documentation › ChartContent.accessibilityHidden(_:)"
PROBE = "Measured: scripts/probes/masking_probe.swift"


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
            id="CHART001",
            title="Copies of one line share a series",
            severity="high",
            source=f"{D_LINEMARK}; {PROBE} §1",
            advice=(
                "Two line plots or marks with the same data and no distinct `series:` are one "
                "series, so Swift Charts draws a segment from the last point of the first copy "
                "back to the first point of the second. A different constant color or opacity "
                "does not separate them. Give each copy its own series, e.g. "
                '`series: .value("Layer", "Dimmed")` and `series: .value("Layer", "Active")`.'
            ),
        ),
        Rule(
            id="CHART002",
            title="Selection slices the plotted data",
            severity="medium",
            source=f"{D_MASK}; {PROBE} §3",
            advice=(
                "Filtering the data up to the selection rebuilds every mark on each drag "
                "event and, with an automatic x domain, rescales the chart as the slice "
                "shrinks. Plot the full data and hide what is past the selection with "
                "`.mask { RectangleMark(xStart:xEnd:) }` instead."
            ),
        ),
        Rule(
            id="CHART003",
            title="Mask edge sits on the first or last data point",
            severity="medium",
            source=PROBE + " §2",
            advice=(
                "A mask rectangle ends exactly at its x value, so a mask from the first data "
                "point cuts away the left half of that point's symbol and line cap (and one "
                "that falls back to the last point, the right half of the last). Start the "
                "mask at the scale's lower bound -- pad the x domain in data units and use "
                "`domain.lowerBound` -- and end it at `domain.upperBound` when nothing is "
                "selected."
            ),
        ),
        Rule(
            id="CHART004",
            title="Mask drawn once per data element",
            severity="low",
            source=f"{PROBE} §2; {S_PLOTS} 11:34",
            advice=(
                "`RectanglePlot(data, xStart:xEnd:)` with constant bounds draws one identical "
                "rectangle per element. A single `RectangleMark(xStart:xEnd:)` (iOS 16) masks "
                "the same pixels."
            ),
        ),
        Rule(
            id="CHART005",
            title="Raw selection value drives a mark",
            severity="medium",
            source=f"{S_SELECT} 5:47; {PROBE} §3–4",
            advice=(
                "The selection binding holds the raw x value under the pointer: past the data "
                "at the plot's padded edges and further still when a drag leaves the plot. "
                "With an automatic x domain a mark at that value widens the domain, so the "
                "chart rescales mid-drag. Snap the value to the nearest element (which also "
                "clamps it) or clamp it to the data range, and give the chart an explicit "
                "`chartXScale(domain:)`."
            ),
        ),
        Rule(
            id="CHART006",
            title="Visual copy of the data is not hidden from accessibility",
            severity="low",
            source=f"{S_RAISE} 4:21; {D_HIDDEN}",
            advice=(
                "Swift Charts makes accessibility elements for chart data by default, so a "
                "dimmed copy or an area under the line can repeat every point to VoiceOver "
                "(inference; not measured). Keep one copy readable and mark the others "
                "`.accessibilityHidden(true)`."
            ),
        ),
        Rule(
            id="CHART007",
            title="Layered copies use different interpolation",
            severity="medium",
            source=f"{S_RAISE} 7:06",
            advice=(
                "Layers meant to sit on top of each other -- the masked line, its dimmed copy, "
                "the area under it -- must share x, y and interpolation method, or the "
                "highlighted part drifts off the dimmed one."
            ),
        ),
        Rule(
            id="CHART008",
            title="Annotation shows the raw selection",
            severity="low",
            source=f"{S_SELECT} 5:47",
            advice=(
                "The binding holds the raw x value; the talk matches it to a data point "
                "first. Formatting the raw value next to a value read from the nearest "
                "element can label one point with another's date -- past the midpoint "
                "between two days the value comes from the next day but the label still names "
                "the previous one. Read both from the matched element."
            ),
        ),
        Rule(
            id="CHART009",
            title="Hand-rolled selection gesture",
            severity="info",
            source=f"{S_SELECT} 5:26, 5:34",
            advice=(
                "A `DragGesture` in `chartOverlay` converting locations with "
                "`proxy.value(atX:)` is the iOS 16 way. From iOS 17, `chartXSelection(value:)` "
                "does the gesture (hover on macOS) and writes the value to a binding; keep "
                "the overlay only when the deployment target is iOS 16."
            ),
        ),
        Rule(
            id="CHART010",
            title="Separate line plots without series are drawn as one line",
            severity="high",
            source=f"{D_LINEMARK}; {PROBE} §1",
            advice=(
                "Every line plot in a chart without a `series:` belongs to one series, whatever "
                "data it holds: Swift Charts connects the plots into one line and draws it in "
                "one style (a dashed plot loses its dash). Give each line its own series. To "
                "draw one line in two styles -- actual and forecast -- plot the full data twice "
                "with complementary masks; plots of the two halves with their own series leave "
                "a gap at the split."
            ),
        ),
    ]
}

INVENTORY_PATTERNS = {
    "Chart": r"\bChart\s*[({]",
    "LinePlot": r"\bLinePlot\s*\(",
    "LineMark": r"\bLineMark\s*\(",
    "AreaPlot": r"\bAreaPlot\s*\(",
    "AreaMark": r"\bAreaMark\s*\(",
    "RuleMark": r"\bRuleMark\s*\(",
    "RectangleMark": r"\bRectangleMark\s*\(",
    "RectanglePlot": r"\bRectanglePlot\s*\(",
    "mask": r"\.\s*mask\s*\{",
    "annotation": r"\.\s*annotation\s*\(",
    "chartXSelection": r"\bchartXSelection\s*\(",
    "chartYSelection": r"\bchartYSelection\s*\(",
    "chartGesture": r"\bchartGesture\s*[({]",
    "chartOverlay": r"\bchartOverlay\s*[({]",
    "chartXScale": r"\bchartXScale\s*\(",
    "series:": r"\bseries\s*:",
    "accessibilityHidden": r"\baccessibilityHidden\s*\(",
    "interpolationMethod": r"\binterpolationMethod\s*\(",
}

LINE_KINDS = {"LinePlot", "LineMark"}
AREA_KINDS = {"AreaPlot", "AreaMark"}
MARK_CALL = re.compile(r"\b(LinePlot|LineMark|AreaPlot|AreaMark)\s*\(")
CHART_OPEN = re.compile(r"\bChart\s*(?=[({])")
SELECTION_BINDING = re.compile(r"\bchart[XY]Selection\s*\(\s*(?:value|range)\s*:\s*\$(\w+)")
OVERLAY_SELECTION = re.compile(r"\b(\w+)\s*=\s*proxy\s*\.\s*value\s*\(\s*atX\s*:")
VALUE_ARG = re.compile(r'\.value\s*\(\s*(?:"(?:[^"\\]|\\.)*"|[^,()]+)\s*,\s*(.+)\)\s*$', re.S)


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


def normalized_value(expression: str | None) -> str | None:
    """`.value("Day", \\.day)` -> `\\.day`; `.value("Day", sample.day)` -> `.day`."""
    if expression is None:
        return None
    match = VALUE_ARG.match(expression.strip())
    inner = match.group(1).strip() if match else expression.strip()
    inner = re.sub(r"\s+", "", inner).lstrip("\\")
    # A LineMark inside ForEach reads `item.day`, a plot `\.day`: compare them as `.day`.
    return re.sub(r"^[A-Za-z_]\w*(?=\.)", "", inner)


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


def mark_calls(code: str, blanked: str, start: int, end: int) -> list[Call]:
    calls: list[Call] = []
    position = start
    while True:
        match = MARK_CALL.search(blanked, position, end)
        if not match:
            break
        parsed = parse_call(code, blanked, match.start(), match.group(1))
        if parsed is None:
            position = match.end()
            continue
        call, _ = parsed
        calls.append(call)
        position = match.end()
    return calls


def mask_closures(code: str, blanked: str, start: int, end: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in re.finditer(r"\.\s*mask\s*\{", blanked[start:end]):
        open_index = start + match.end() - 1
        close_index = matching(blanked, open_index)
        if close_index != -1:
            ranges.append((open_index + 1, close_index))
    return ranges


def resolve(identifier: str, scopes: list[str]) -> str:
    """Follow `let name = expression` / `if let name = expression` one step."""
    pattern = re.compile(r"\b(?:let|var)\s+" + re.escape(identifier) + r"\b\s*(?::[^=\n]+)?=\s*([^\n{]+)")
    for scope in scopes:
        match = pattern.search(scope)
        if match:
            return match.group(1).strip().rstrip(",")
    return identifier


EDGE_START = re.compile(r"\.\s*first\b|\.\s*min\s*\(|\[\s*0\s*\]|\.\s*startIndex\b")
EDGE_END = re.compile(r"\.\s*last\b|\.\s*max\s*\(|\.\s*endIndex\b")
# Default-argument scan for the value inside `.value("Label", expr)`.
VALUE_EXPR = re.compile(r'\.value\s*\(\s*(?:"(?:[^"\\]|\\.)*"|[^,()]+)\s*,\s*([^()]+?)\s*\)\s*$', re.S)


def value_expression(argument: str | None) -> str | None:
    if argument is None:
        return None
    match = VALUE_EXPR.match(argument.strip())
    return match.group(1).strip() if match else None


def touches_edge(expression: str, scopes: list[str], edge: re.Pattern[str], fallback_only: bool) -> bool:
    """Does `expression` (or what its identifiers are bound to) name the data's first/last element?"""
    candidates = [expression]
    if fallback_only:
        if "??" not in expression:
            return False
        candidates = [expression.split("??", 1)[1].strip()]
    for candidate in candidates:
        if edge.search(candidate):
            return True
        if re.fullmatch(r"[A-Za-z_]\w*", candidate):
            if edge.search(resolve(candidate, scopes)):
                return True
    return False


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


def layer_key(call: Call) -> tuple[str, str, str] | None:
    """What a layer plots: (data, x, y). LineMark has no data argument; '' matches any."""
    x = normalized_value(call.args.get("x"))
    y = normalized_value(call.args.get("y"))
    if x is None or y is None:
        return None
    data = re.sub(r"\s+", "", call.positional[0]) if call.kind.endswith("Plot") and call.positional else ""
    return data, x, y


def interpolation(call: Call) -> str:
    return re.sub(r"\s+", "", call.modifier("interpolationMethod") or "(.linear)")


def layer_groups(layers: list[Call]) -> list[list[Call]]:
    """Layers that draw the same data on the same x and y, in declaration order.

    A plot names its data; a mark inside `ForEach` does not, so it joins every group
    on its x and y. Two plots of different collections are different layers.
    """
    by_axes: dict[tuple[str, str], list[tuple[str, Call]]] = {}
    for call in layers:
        key = layer_key(call)
        if key is None:
            continue
        data, x, y = key
        by_axes.setdefault((x, y), []).append((data, call))
    groups: list[list[Call]] = []
    for members in by_axes.values():
        named = sorted({data for data, _ in members if data})
        if not named:
            groups.append([call for _, call in members])
            continue
        for name in named:
            groups.append([call for data, call in members if data in (name, "")])
    return groups


def scan_chart(rel: str, text: str, code: str, blanked: str, start: int, end: int, selections: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    calls = mark_calls(code, blanked, start, end)
    masks = mask_closures(code, blanked, start, end)
    in_mask = lambda call: any(a <= call.start < b for a, b in masks)  # noqa: E731
    layers = [call for call in calls if not in_mask(call)]

    for members in layer_groups(layers):
        # CHART001: copies of one line in one series.
        lines = [call for call in members if call.kind in LINE_KINDS]
        styled_by_value = any("by:" in (call.modifier("foregroundStyle") or "") for call in lines)
        if len(lines) > 1 and not styled_by_value:
            seen: set[str] = set()
            for call in lines:
                series = re.sub(r"\s+", "", call.args.get("series", ""))
                if series in seen:
                    findings.append(make_finding("CHART001", rel, text, call.start))
                seen.add(series)

        # CHART007: layers of the same data with different interpolation.
        if len(members) > 1:
            reference = interpolation(members[0])
            for call in members[1:]:
                if interpolation(call) != reference:
                    findings.append(make_finding("CHART007", rel, text, call.start))
                    break

        # CHART006: more than one copy readable by VoiceOver.
        if len(members) > 1:
            readable = [call for call in members if "true" not in (call.modifier("accessibilityHidden") or "")]
            if len(readable) > 1:
                findings.append(make_finding("CHART006", rel, text, readable[1].start))

    # CHART010: line plots of different data, none with a series, merge into one line.
    unseriesed: dict[str, Call] = {}
    for call in layers:
        if call.kind != "LinePlot" or not call.positional or "series" in call.args:
            continue
        if "by:" in (call.modifier("foregroundStyle") or ""):
            continue
        data = re.sub(r"\s+", "", call.positional[0])
        if data not in unseriesed:
            if unseriesed:
                findings.append(make_finding("CHART010", rel, text, call.start))
            unseriesed[data] = call

    # Masks: CHART003 (edge on a data point) and CHART004 (one rectangle per element).
    for mask_start, mask_end in masks:
        scopes = [code[mask_start:mask_end], code]
        for match in re.finditer(r"\b(RectangleMark|RectanglePlot)\s*\(", blanked[mask_start:mask_end]):
            parsed = parse_call(code, blanked, mask_start + match.start(), match.group(1))
            if parsed is None:
                continue
            rectangle, _ = parsed
            x_start = value_expression(rectangle.args.get("xStart"))
            x_end = value_expression(rectangle.args.get("xEnd"))
            if (x_start and touches_edge(x_start, scopes, EDGE_START, fallback_only=False)) or (
                x_end and touches_edge(x_end, scopes, EDGE_END, fallback_only=True)
            ):
                findings.append(make_finding("CHART003", rel, text, rectangle.start))
            if rectangle.kind == "RectanglePlot" and any(
                expression is not None and not expression.startswith("\\")
                for expression in (x_start, x_end)
            ):
                findings.append(make_finding("CHART004", rel, text, rectangle.start))

    # CHART005: a selection variable used as a mark's value without clamping or snapping.
    for name in selections:
        clamped = re.search(
            r"onChange\s*\(\s*of\s*:\s*" + re.escape(name) + r"\b[\s\S]{0,600}?(?:\bmin\s*\(|\bmax\s*\(|clamp)", code
        ) or re.search(r"\b" + re.escape(name) + r"\s*=\s*(?:min|max|clamp)", code)
        if clamped:
            continue
        usage = re.compile(r'\.value\s*\(\s*"(?:[^"\\]|\\.)*"\s*,\s*' + re.escape(name) + r"\b(?!\s*\.)")
        match = usage.search(code, start, end)
        if match:
            findings.append(make_finding("CHART005", rel, text, match.start()))

    # CHART008: the raw selection formatted inside an annotation.
    for match in re.finditer(r"\.\s*annotation\s*\(", blanked[start:end]):
        open_index = start + match.end() - 1
        close_index = matching(blanked, open_index)
        if close_index == -1:
            continue
        trailing = re.match(r"\s*\{", blanked[close_index + 1 :])
        body_end = close_index
        if trailing:
            brace = close_index + 1 + trailing.end() - 1
            body_end = matching(blanked, brace)
        if body_end == -1:
            continue
        body = code[open_index:body_end]
        for name in selections:
            raw = re.search(
                r"\bText\s*\(\s*" + re.escape(name) + r"\b(?!\s*[.?])|\b" + re.escape(name) + r"\s*\??\s*\.\s*formatted\s*\(|\\\(\s*" + re.escape(name) + r"\b(?!\s*[.?])",
                body,
            )
            if raw:
                findings.append(make_finding("CHART008", rel, text, open_index + raw.start()))
                break
    return findings


def scan_source(rel: str, text: str) -> tuple[list[Finding], dict[str, int]]:
    code = strip_comments(text)
    blanked = blank_strings(code)
    inventory = {name: len(re.findall(pattern, blanked if name != "series:" else code)) for name, pattern in INVENTORY_PATTERNS.items()}
    selections = set(SELECTION_BINDING.findall(code)) | set(OVERLAY_SELECTION.findall(code))
    findings: list[Finding] = []
    for start, end in chart_blocks(code, blanked):
        findings.extend(scan_chart(rel, text, code, blanked, start, end, selections))

    # CHART002: data filtered or cut by a selection variable.
    for name in selections:
        slicing = re.compile(
            r"\.\s*(?:filter|prefix\s*\(\s*while\s*:)\s*\(?\s*\{[^{}]*\b" + re.escape(name) + r"\b"
            r"|\.\s*prefix\s*\(\s*while\s*:\s*\{[^{}]*\b" + re.escape(name) + r"\b"
        )
        for match in slicing.finditer(code):
            findings.append(make_finding("CHART002", rel, text, match.start()))

    # CHART009: a DragGesture over the chart converted with proxy.value(atX:).
    if re.search(r"\bchartOverlay\b", blanked) and re.search(r"\bDragGesture\s*\(", blanked):
        match = re.search(r"\bvalue\s*\(\s*atX\s*:", blanked)
        if match:
            findings.append(make_finding("CHART009", rel, text, match.start()))

    # One finding per rule and line.
    unique: dict[str, Finding] = {}
    for finding in findings:
        unique.setdefault(finding.id, finding)
    return list(unique.values()), inventory


def scan(root: Path, include_dependencies: bool = False) -> dict:
    root = root.resolve()
    files = iter_project_files(root, include_dependencies)
    findings: list[Finding] = []
    inventory = {name: 0 for name in INVENTORY_PATTERNS}
    chart_files: list[str] = []
    source_count = 0
    for path in files:
        if path.suffix != ".swift":
            continue
        text = read_text(path)
        if text is None:
            continue
        source_count += 1
        rel = relative(path, root)
        file_findings, counts = scan_source(rel, text)
        findings.extend(file_findings)
        for name, count in counts.items():
            inventory[name] += count
        if counts["Chart"]:
            chart_files.append(rel)

    findings.sort(key=lambda f: (SEVERITIES.index(f.severity), f.rule, f.file, f.line))
    by_severity = {severity: 0 for severity in SEVERITIES}
    by_rule: dict[str, int] = {}
    for finding in findings:
        by_severity[finding.severity] += 1
        by_rule[finding.rule] = by_rule.get(finding.rule, 0) + 1

    return {
        "tool": "charts_scan",
        "version": VERSION,
        "root": str(root),
        "read_only": True,
        "source_files_scanned": source_count,
        "dependencies_included": include_dependencies,
        "project": {
            "ios_deployment_targets": deployment_targets(root, files),
            "files_with_charts": chart_files,
        },
        "summary": {"by_severity": by_severity, "by_rule": by_rule},
        "findings": [asdict(finding) for finding in findings],
        "inventory": {name: count for name, count in inventory.items() if count},
    }


def render_markdown(report: dict, limit: int) -> str:
    targets = ", ".join(report["project"]["ios_deployment_targets"]) or "not found"
    lines = [
        "# Swift Charts masking scan",
        "",
        f"- Root: `{report['root']}`",
        f"- Swift files scanned: {report['source_files_scanned']}",
        f"- Files with charts: {len(report['project']['files_with_charts'])}",
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
