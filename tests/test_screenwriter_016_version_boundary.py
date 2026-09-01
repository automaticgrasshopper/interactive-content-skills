from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_SKILL = ROOT / "business-skill-track/episode-skill-split/versions/0.15/episode-screenwriter-biz"
CURRENT_SKILL = ROOT / "business-skill-track/episode-skill-split/versions/0.16/episode-screenwriter-biz"
LOCAL_METADATA = {Path("reference-manifest.json")}
INTENTIONAL_RUNTIME_CHANGES: set[Path] = set()


def runtime_files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if (
            path.is_file()
            and path.relative_to(root) not in LOCAL_METADATA
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
        )
    }


class ScreenwriterVersionBoundaryTests(unittest.TestCase):
    def test_current_skill_starts_from_declared_base_without_mixed_capabilities(self) -> None:
        base_files = runtime_files(BASE_SKILL)
        current_files = runtime_files(CURRENT_SKILL)

        self.assertEqual(set(current_files) - set(base_files), INTENTIONAL_RUNTIME_CHANGES)
        self.assertEqual(set(base_files) - set(current_files), set())
        for relative_path in sorted(set(base_files) - INTENTIONAL_RUNTIME_CHANGES):
            self.assertEqual(current_files[relative_path], base_files[relative_path], str(relative_path))

    def test_skill_package_has_no_release_version_awareness(self) -> None:
        self.assertFalse((CURRENT_SKILL / "reference-manifest.json").exists())
        for path in CURRENT_SKILL.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("episode-screenwriter-biz/0.", text, str(path))
            self.assertNotIn("0.15", text, str(path))
            self.assertNotIn("0.16", text, str(path))
            self.assertNotIn("SKILL_VERSION", text, str(path))


if __name__ == "__main__":
    unittest.main()
