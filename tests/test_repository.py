from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"

EXPECTED_SKILLS = {
    "episode-generator",
    "nxp-episode-checker",
    "nxp-plan-storyboard-and-generate-episode-zh",
    "outline-generator",
    "split-video",
    "互动影像资产图像提示词生成",
    "剧本实例化专家",
    "剧本转分镜图",
    "导演分镜故事版拓展能力",
    "故事结构专家",
    "节奏题材校验专家",
    "角色三视图设定表生成能力",
}


class RepositoryTests(unittest.TestCase):
    def test_exactly_twelve_formal_skills_are_present(self) -> None:
        actual = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
        self.assertEqual(actual, EXPECTED_SKILLS)

    def test_each_skill_has_name_and_description_frontmatter(self) -> None:
        names = set()
        for folder in sorted(SKILLS_ROOT.iterdir()):
            text = (folder / "SKILL.md").read_text(encoding="utf-8")
            match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
            self.assertIsNotNone(match, f"{folder.name} 缺少 YAML frontmatter")
            frontmatter = match.group(1)
            name_match = re.search(r"^name:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
            self.assertIsNotNone(name_match, f"{folder.name} 缺少 name")
            self.assertRegex(frontmatter, r"(?m)^description:\s*(?:.+|[>|]-?)$")
            name = name_match.group(1).strip("\"'")
            self.assertNotIn(name, names, f"重复 Skill name：{name}")
            names.add(name)
        self.assertEqual(len(names), 12)

    def test_internal_references_exist(self) -> None:
        pattern = re.compile(r"(?:references|scripts)/[^\s`，。；：）)]+")
        for folder in sorted(SKILLS_ROOT.iterdir()):
            text = (folder / "SKILL.md").read_text(encoding="utf-8")
            for relative in pattern.findall(text):
                self.assertTrue(
                    (folder / relative).is_file(),
                    f"{folder.name} 引用了不存在的 {relative}",
                )

    def test_skills_have_no_platform_runtime_dependency(self) -> None:
        forbidden = (
            "interactive-drama-lab",
            "backend/production_worker.py",
            "h5/影视互动游戏故事节奏验证.html",
        )
        for path in SKILLS_ROOT.rglob("*"):
            if not path.is_file() or path.suffix in {".pyc", ".pyo"}:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, text, f"{path} contains {marker}")

    def test_episode_generator_manifest_is_v047(self) -> None:
        manifest = json.loads(
            (
                SKILLS_ROOT
                / "episode-generator"
                / "reference-manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["skill_version"], "v0.1.47")


if __name__ == "__main__":
    unittest.main()
