#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
TRACK = PIPELINE.parent
VERSION = PIPELINE / "versions/0.02"
UPLOAD = PIPELINE / "upload/0.02"
SOURCE = TRACK / "episode-generator-biz/0.46"
SKILLS = {
    "episode-branch-planner-biz": VERSION / "episode-branch-planner-biz",
    "episode-screenwriter-biz": VERSION / "episode-screenwriter-biz",
    "episode-script-validator-biz": VERSION / "episode-script-validator-biz",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SkillPartitionTests(unittest.TestCase):
    def test_frontmatter_references_scripts_and_ui_metadata(self) -> None:
        for slug, root in SKILLS.items():
            text = (root / "SKILL.md").read_text(encoding="utf-8")
            match = re.match(r"^---\nname: ([^\n]+)\ndescription: \"(.+?)\"\n---\n", text, re.S)
            self.assertIsNotNone(match, slug)
            self.assertEqual(match.group(1), slug)
            self.assertLessEqual(len(match.group(2)), 1024)
            for reference in set(re.findall(r"references/([A-Za-z0-9_.-]+)", text)):
                self.assertTrue((root / "references" / reference).is_file(), f"{slug}: {reference}")
            for script in set(re.findall(r"scripts/([A-Za-z0-9_.-]+\.py)", text)):
                self.assertTrue((root / "scripts" / script).is_file(), f"{slug}: {script}")
            agent_yaml = (root / "agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn(f"${slug}", agent_yaml)
            manifest = json.loads((root / "reference-manifest.json").read_text(encoding="utf-8"))
            for names in manifest["phases"].values():
                for name in names:
                    self.assertTrue((root / "references" / name).is_file(), f"{slug}: {name}")

    def test_stage_ownership_is_enforced_by_package_contents(self) -> None:
        planner_scripts = {p.name for p in (SKILLS["episode-branch-planner-biz"] / "scripts").glob("*.py")}
        writer_scripts = {p.name for p in (SKILLS["episode-screenwriter-biz"] / "scripts").glob("*.py")}
        validator_scripts = {p.name for p in (SKILLS["episode-script-validator-biz"] / "scripts").glob("*.py")}
        self.assertNotIn("assemble_business_output.py", planner_scripts)
        self.assertNotIn("build_enhancer_input.py", planner_scripts)
        self.assertNotIn("assemble_business_output.py", writer_scripts)
        self.assertNotIn("build_enhancer_input.py", writer_scripts)
        self.assertIn("build_enhancer_input.py", validator_scripts)
        self.assertIn("assemble_business_output.py", validator_scripts)
        self.assertIn("verify_deliverable.py", validator_scripts)
        self.assertIn("pipeline_guard.py", validator_scripts)

    def test_validator_preserves_original_business_implementation(self) -> None:
        validator = SKILLS["episode-script-validator-biz"]
        for source_file in (SOURCE / "scripts").glob("*.py"):
            copied = validator / "scripts" / source_file.name
            self.assertTrue(copied.is_file(), source_file.name)
            self.assertEqual(digest(source_file), digest(copied), source_file.name)
        for source_file in (SOURCE / "references").glob("*.md"):
            copied = validator / "references" / source_file.name
            self.assertTrue(copied.is_file(), source_file.name)
            if source_file.name != "external-output-boundary.md":
                self.assertEqual(digest(source_file), digest(copied), source_file.name)

    def test_handoff_implementation_is_identical_across_skills(self) -> None:
        hashes = {
            digest(root / "scripts/stage_handoff.py")
            for root in SKILLS.values()
        }
        self.assertEqual(len(hashes), 1)

    def test_pipeline_guard_is_identical_across_skills(self) -> None:
        hashes = {digest(root / "scripts/pipeline_guard.py") for root in SKILLS.values()}
        self.assertEqual(len(hashes), 1)

    def test_coordinator_and_worker_boundaries_are_explicit(self) -> None:
        planner = (SKILLS["episode-branch-planner-biz"] / "SKILL.md").read_text(encoding="utf-8")
        writer = (SKILLS["episode-screenwriter-biz"] / "SKILL.md").read_text(encoding="utf-8")
        validator = (SKILLS["episode-script-validator-biz"] / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("STAGE_WORKER:planning", planner)
        self.assertIn("全新子任务", planner)
        self.assertIn("STAGE_WORKER:writing", writer)
        self.assertIn("STAGE_WORKER:validation", validator)
        self.assertIn("PROJECTION_AUTHORIZATION_CREATED", validator)

    def test_frozen_baseline_hashes_match(self) -> None:
        baseline = json.loads((Path(__file__).with_name("baseline.json")).read_text(encoding="utf-8"))
        for name, expected in baseline["files"].items():
            self.assertEqual(digest(SOURCE / name), expected, name)

    def test_upload_mirror_matches_version_archive(self) -> None:
        for slug, root in SKILLS.items():
            version_files = sorted(
                path.relative_to(root)
                for path in root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            )
            upload_root = UPLOAD / slug
            upload_files = sorted(
                path.relative_to(upload_root)
                for path in upload_root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            )
            self.assertEqual(version_files, upload_files, slug)
            for name in version_files:
                self.assertEqual(digest(root / name), digest(upload_root / name), f"{slug}: {name}")


if __name__ == "__main__":
    unittest.main()
