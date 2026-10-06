#!/usr/bin/env python3
"""Typecheck every tagged Swift block in the skills' references against the installed SDK.

A block whose first line is `// typecheck: ios<N>` must compile for iOS N and,
unless N is the oldest version Swift Charts supports, fail for iOS N-1: the second
run is what checks the block's availability claim, not just its syntax.
`// typecheck: ios<N>.<M>` names a point release: the block must compile for iOS N.M
and fail for iOS N.(M-1). `// typecheck: ios<N>, continues the block above` compiles
the block together with the one before it. Blocks without the tag are fragments and
are skipped.

    python3 scripts/typecheck_samples.py            # all references
    python3 scripts/typecheck_samples.py --list     # what would be checked
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"```swift\n(.*?)```", re.S)
TAG = re.compile(r"^// typecheck: ios(\d+)(?:\.(\d+))?(, continues the block above)?\s*$", re.M)
OLDEST_CHARTS_IOS = 16


@dataclass
class Sample:
    source: Path
    index: int
    ios: int
    code: str
    minor: int = 0

    @property
    def version(self) -> str:
        return f"{self.ios}.{self.minor}"

    @property
    def below(self) -> str | None:
        """The release one step down, which must reject the block; None at the oldest."""
        if self.minor:
            return f"{self.ios}.{self.minor - 1}"
        if self.ios > OLDEST_CHARTS_IOS:
            return f"{self.ios - 1}.0"
        return None


def samples(paths: list[Path]) -> list[Sample]:
    found: list[Sample] = []
    for path in paths:
        previous: str | None = None
        for index, match in enumerate(BLOCK.finditer(path.read_text(encoding="utf-8")), start=1):
            code = match.group(1)
            first_line = code.split("\n", 1)[0]
            tag = TAG.match(first_line)
            if not tag:
                previous = None
                continue
            body = code.split("\n", 1)[1] if "\n" in code else ""
            if tag.group(3):
                if previous is None:
                    raise SystemExit(f"{path}: block {index} continues a block that is not tagged")
                body = previous + "\n" + body
            found.append(Sample(path, index, int(tag.group(1)), body, int(tag.group(2) or 0)))
            previous = body
    return found


def typecheck(code: str, ios: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        file = Path(directory) / "Sample.swift"
        file.write_text(code, encoding="utf-8")
        return subprocess.run(
            [
                "xcrun", "--sdk", "iphonesimulator", "swiftc", "-typecheck",
                "-target", f"arm64-apple-ios{ios}-simulator", str(file),
            ],
            capture_output=True,
            text=True,
        )


def reference_files() -> list[Path]:
    return sorted((ROOT / "skills").glob("*/references/*.md"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="Markdown files; defaults to skills/*/references/*.md")
    parser.add_argument("--list", action="store_true", help="List the tagged blocks without compiling")
    args = parser.parse_args(argv)

    found = samples([path.resolve() for path in args.files] or reference_files())
    if args.list:
        for sample in found:
            print(f"{sample.source.relative_to(ROOT)} block {sample.index}: iOS {sample.version}")
        return 0
    if shutil.which("xcrun") is None:
        print("xcrun not found: typechecking needs Xcode", file=sys.stderr)
        return 3

    failures = 0
    for sample in found:
        label = f"{sample.source.relative_to(ROOT)} block {sample.index}"
        result = typecheck(sample.code, sample.version)
        if result.returncode != 0:
            failures += 1
            print(f"FAIL {label}: does not compile for iOS {sample.version}\n{result.stderr}")
            continue
        if sample.below:
            below = typecheck(sample.code, sample.below)
            if below.returncode == 0:
                failures += 1
                print(f"FAIL {label}: also compiles for iOS {sample.below}; lower its tag")
                continue
        print(f"ok   {label}: iOS {sample.version}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
