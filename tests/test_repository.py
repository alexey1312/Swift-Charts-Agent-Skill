from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILLS = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())


def frontmatter(skill: str) -> dict[str, str]:
    text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, f"{skill}: missing frontmatter"
    fields: dict[str, str] = {}
    current = None
    for line in match.group(1).splitlines():
        if re.match(r"^[a-z_-]+:", line):
            key, _, value = line.partition(":")
            current = key.strip()
            fields[current] = value.strip()
        elif current:
            fields[current] = (fields[current] + " " + line.strip()).strip()
    if fields.get("description", "").startswith(">-"):
        fields["description"] = fields["description"][2:].strip()
    return fields


class ManifestTests(unittest.TestCase):
    def test_json_manifests_parse(self) -> None:
        for relative in (
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            ".cursor-plugin/plugin.json",
            "package.json",
        ):
            with self.subTest(relative):
                json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_every_manifest_lists_every_skill(self) -> None:
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        cursor = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text(encoding="utf-8"))
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        for name, paths in (
            ("plugin.json", plugin["skills"]),
            ("cursor plugin.json", cursor["skills"]),
            ("package.json", package["pi"]["skills"]),
        ):
            with self.subTest(name):
                self.assertEqual(sorted(Path(p).name for p in paths), SKILLS)
                for path in paths:
                    self.assertTrue((ROOT / path / "SKILL.md").is_file(), path)

    def test_versions_agree(self) -> None:
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        cursor = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text(encoding="utf-8"))
        entry = next(p for p in marketplace["plugins"] if p["name"] == plugin["name"])
        self.assertEqual(marketplace["version"], plugin["version"])
        self.assertEqual(entry["version"], plugin["version"])
        self.assertEqual(cursor["version"], plugin["version"])
        openai = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn(f'version: "{plugin["version"]}"', openai)
        for skill in SKILLS:
            self.assertIn(f"  - {skill}\n", openai)


class SkillTests(unittest.TestCase):
    def test_frontmatter(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill):
                fields = frontmatter(skill)
                self.assertEqual(fields.get("name"), skill)
                description = fields.get("description", "")
                self.assertGreater(len(description), 200)
                self.assertLessEqual(len(description), 1024)

    def test_referenced_files_exist(self) -> None:
        pattern = re.compile(r"`((?:references|scripts)/[\w./-]+\.(?:md|py|swift))")
        for skill in SKILLS:
            directory = ROOT / "skills" / skill
            for document in [directory / "SKILL.md", *sorted((directory / "references").glob("*.md"))]:
                text = document.read_text(encoding="utf-8")
                for relative in set(pattern.findall(text)):
                    with self.subTest(file=document.name, reference=relative):
                        in_skill = (directory / relative).is_file()
                        in_skill_references = (directory / "references" / Path(relative).name).is_file()
                        in_repository = (ROOT / relative).is_file()
                        self.assertTrue(in_skill or in_skill_references or in_repository, relative)

    def test_sibling_references_named_in_prose_exist(self) -> None:
        pattern = re.compile(r"`([a-z-]+\.md)`")
        for skill in SKILLS:
            references = ROOT / "skills" / skill / "references"
            names = {path.name for path in references.glob("*.md")}
            for document in [ROOT / "skills" / skill / "SKILL.md", *sorted(references.glob("*.md"))]:
                for name in set(pattern.findall(document.read_text(encoding="utf-8"))):
                    with self.subTest(file=document.name, reference=name):
                        self.assertTrue(name in names or (ROOT / name).is_file(), name)

    def test_measured_sections_exist(self) -> None:
        pattern = re.compile(r"measured-behavior\.md` §(\d)|\(\*Measured\* §(\d)")
        for skill in SKILLS:
            directory = ROOT / "skills" / skill
            measured = (directory / "references" / "measured-behavior.md").read_text(encoding="utf-8")
            sections = set(re.findall(r"^## §(\d)", measured, re.M))
            for document in [directory / "SKILL.md", *sorted((directory / "references").glob("*.md")), ROOT / "CHECKS.md"]:
                for match in pattern.findall(document.read_text(encoding="utf-8")):
                    section = match[0] or match[1]
                    with self.subTest(file=document.name, section=section):
                        self.assertIn(section, sections)


class EvalTests(unittest.TestCase):
    def test_every_skill_has_skill_creator_evals(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill):
                directory = ROOT / "skills" / skill / "evals"
                evals = json.loads((directory / "evals.json").read_text(encoding="utf-8"))
                self.assertEqual(evals["skill_name"], skill)
                ids = [item["id"] for item in evals["evals"]]
                self.assertEqual(len(ids), len(set(ids)))
                for item in evals["evals"]:
                    self.assertTrue(item["expectations"])
                    for relative in item["files"]:
                        self.assertTrue((ROOT / "skills" / skill / relative).exists(), relative)

    def test_trigger_evals_mix_positive_and_negative(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill):
                path = ROOT / "skills" / skill / "evals" / "trigger-evals.json"
                items = json.loads(path.read_text(encoding="utf-8"))
                self.assertGreaterEqual(len(items), 16)
                positives = sum(item["should_trigger"] for item in items)
                self.assertGreaterEqual(positives, 6)
                self.assertGreaterEqual(len(items) - positives, 6)


if __name__ == "__main__":
    unittest.main()
