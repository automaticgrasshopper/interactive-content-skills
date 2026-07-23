from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "episode-generator"


class SkillPackageTests(unittest.TestCase):
    def test_package_contains_only_runtime_files(self) -> None:
        files = {
            path.relative_to(SKILL_ROOT).as_posix()
            for path in SKILL_ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and ".DS_Store" not in path.parts
        }
        self.assertEqual(
            files,
            {
                "SKILL.md",
                "agents/openai.yaml",
                "reference-manifest.json",
                "references/causal-episode-writing.md",
                "references/chinese-dialogue-craft.md",
                "references/emotional-spine-state-graph.md",
                "references/episode-quality-review.md",
                "references/public-output-and-progress.md",
                "references/upstream-input-translation.md",
                "references/written-text-to-dialogue.md",
                "scripts/episode_quality_gate.py",
                "scripts/validate_and_assemble_scripts.py",
                "scripts/validate_emotional_topology.py",
                "scripts/validate_topology.py",
            },
        )

    def test_manifest_and_skill_declare_v047(self) -> None:
        manifest = json.loads(
            (SKILL_ROOT / "reference-manifest.json").read_text(encoding="utf-8")
        )
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(manifest["skill_version"], "v0.1.47")
        self.assertIn("# 分集规划师", skill)
        self.assertNotIn("当前规范版本：", skill)

    def test_skill_has_no_platform_runtime_dependency(self) -> None:
        forbidden = (
            "interactive-drama-lab",
            "backend/production_worker.py",
            "h5/影视互动游戏故事节奏验证.html",
        )
        for path in SKILL_ROOT.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix in {".pyc", ".pyo"}
            ):
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, text, f"{path} contains {marker}")


if __name__ == "__main__":
    unittest.main()
