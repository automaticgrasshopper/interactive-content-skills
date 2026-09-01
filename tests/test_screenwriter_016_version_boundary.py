from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_SKILL = ROOT / "business-skill-track/episode-skill-split/versions/0.12/episode-screenwriter-biz"
CURRENT_SKILL = ROOT / "business-skill-track/episode-skill-split/versions/0.16/episode-screenwriter-biz"
LOCAL_METADATA = {Path("reference-manifest.json")}
INTENTIONAL_RUNTIME_CHANGES = {
    Path("SKILL.md"),
    Path("references/business-interface.md"),
    Path("references/compact-action-draft.md"),
    Path("references/dialogue-and-quality.md"),
    Path("references/full-scene-enhancer.md"),
    Path("references/node-screenwriting.md"),
    Path("references/post-acceptance-revision.md"),
    Path("scripts/accept_node_screenplay.py"),
    Path("scripts/build_node_writing_packet.py"),
    Path("scripts/screenplay_contract.py"),
    Path("scripts/stage_contract.py"),
}
INTENTIONAL_RUNTIME_ADDITIONS = {
    Path("references/romance-scene-realization.md"),
    Path("scripts/build_episode_plan_index.py"),
    Path("scripts/episode_plan_index.py"),
}


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

        self.assertEqual(set(base_files) - set(current_files), set())
        self.assertEqual(set(current_files) - set(base_files), INTENTIONAL_RUNTIME_ADDITIONS)
        changed_files = {
            relative_path
            for relative_path in set(base_files) & set(current_files)
            if current_files[relative_path] != base_files[relative_path]
        }
        self.assertEqual(changed_files, INTENTIONAL_RUNTIME_CHANGES)
        for relative_path in sorted(set(base_files) - INTENTIONAL_RUNTIME_CHANGES):
            self.assertEqual(current_files[relative_path], base_files[relative_path], str(relative_path))

    def test_skill_package_has_no_release_version_awareness(self) -> None:
        self.assertFalse((CURRENT_SKILL / "reference-manifest.json").exists())
        for path in CURRENT_SKILL.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("episode-screenwriter-biz/0.", text, str(path))
            self.assertNotIn("episode-route-planner-biz/0.", text, str(path))
            self.assertNotIn("0.12", text, str(path))
            self.assertNotIn("0.16", text, str(path))
            self.assertNotIn("SKILL_VERSION", text, str(path))
            self.assertNotIn("ROUTE_SKILL_VERSION", text, str(path))
            self.assertNotIn("skill_version", text, str(path))

    def test_runtime_contract_keeps_business_identity_without_release_identity(self) -> None:
        contract_path = CURRENT_SKILL / "scripts/screenplay_contract.py"
        spec = importlib.util.spec_from_file_location("screenwriter_016_contract", contract_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)

        self.assertEqual(module.CAPABILITY_ID, "episode-screenwriter-biz")
        self.assertEqual(module.ROUTE_CAPABILITY_ID, "episode-route-planner-biz")
        self.assertNotIn("skill_version", module.PATCH_FIELDS)
        self.assertFalse(hasattr(module, "SKILL_VERSION"))
        self.assertFalse(hasattr(module, "ROUTE_SKILL_VERSION"))


if __name__ == "__main__":
    unittest.main()
