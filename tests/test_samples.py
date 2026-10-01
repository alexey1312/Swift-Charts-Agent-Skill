from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("typecheck_samples", ROOT / "scripts" / "typecheck_samples.py")
assert SPEC and SPEC.loader
typecheck_samples = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = typecheck_samples
SPEC.loader.exec_module(typecheck_samples)


class ExtractionTests(unittest.TestCase):
    def test_tags_continuations_and_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            path.write_text(
                "```swift\n// typecheck: ios18\nlet a = 1\n```\n"
                "```swift\n// typecheck: ios18, continues the block above\nlet b = a\n```\n"
                "```swift\nlet fragment = 1\n```\n",
                encoding="utf-8",
            )
            found = typecheck_samples.samples([path])
        self.assertEqual([(s.index, s.ios) for s in found], [(1, 18), (2, 18)])
        self.assertIn("let a = 1", found[1].code)
        self.assertIn("let b = a", found[1].code)

    def test_every_reference_block_is_tagged(self) -> None:
        # A fragment would silently escape the typecheck; references hold complete code.
        for path in typecheck_samples.reference_files():
            text = path.read_text(encoding="utf-8")
            blocks = text.count("```swift\n")
            tagged = len(typecheck_samples.TAG.findall(text))
            with self.subTest(path.name):
                self.assertEqual(blocks, tagged)


@unittest.skipUnless(shutil.which("xcrun"), "needs Xcode")
class TypecheckTests(unittest.TestCase):
    def test_reference_samples_compile_at_their_floor(self) -> None:
        self.assertEqual(typecheck_samples.main([]), 0)


if __name__ == "__main__":
    unittest.main()
