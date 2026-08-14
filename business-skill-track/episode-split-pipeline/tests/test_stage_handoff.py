#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
MODULE_PATH = PIPELINE / "versions/0.02/episode-branch-planner-biz/scripts/stage_handoff.py"
SPEC = importlib.util.spec_from_file_location("stage_handoff", MODULE_PATH)
assert SPEC and SPEC.loader
stage_handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage_handoff)
GUARD_PATH = PIPELINE / "versions/0.02/episode-branch-planner-biz/scripts/pipeline_guard.py"
GUARD_SPEC = importlib.util.spec_from_file_location("pipeline_guard", GUARD_PATH)
assert GUARD_SPEC and GUARD_SPEC.loader
pipeline_guard = importlib.util.module_from_spec(GUARD_SPEC)
GUARD_SPEC.loader.exec_module(pipeline_guard)


class StageHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in stage_handoff.PLANNING_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".json":
                payload = {"issues": []} if name.endswith("review.json") else {"fixture": name}
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            else:
                path.write_text(f"fixture:{name}\n", encoding="utf-8")
        synopsis_dir = self.root / "episode-synopses"
        synopsis_dir.mkdir()
        for episode_id in ("episode-001", "episode-002"):
            (synopsis_dir / f"{episode_id}.json").write_text(
                json.dumps({"episode_id": episode_id}, ensure_ascii=False), encoding="utf-8"
            )
        self.planning = self.root / "planning-handoff.json"
        self.state = self.root / "pipeline-state.json"
        self.planning_ticket = self.root / "planning-ticket.json"
        pipeline_guard.init_state(self.state)
        pipeline_guard.issue_ticket(self.state, "planning", self.planning_ticket)
        pipeline_guard.claim_ticket(self.state, "planning", self.planning_ticket)
        stage_handoff.create_planning(self.root, self.planning, self.state)
        pipeline_guard.accept_handoff(self.state, "planning", self.planning_ticket, self.planning)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create_writing_files(self) -> None:
        for episode_id in ("episode-001", "episode-002"):
            for pattern in stage_handoff.WRITING_PATTERNS:
                path = self.root / pattern.format(episode_id=episode_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                if "screenwriter-receipts" in pattern:
                    continue
                if path.suffix == ".json":
                    path.write_text(json.dumps({"episode_id": episode_id}), encoding="utf-8")
                else:
                    path.write_text(f"{episode_id} complete screenplay\n", encoding="utf-8")
            draft = self.root / f"screenplay-drafts/{episode_id}.md"
            receipt = {
                "contract_version": "nextplay.screenwriter-receipt.v1",
                "episode_id": episode_id,
                "draft_sha256": stage_handoff.sha256(draft),
                "status": "PASS",
            }
            (self.root / f"screenwriter-receipts/{episode_id}.json").write_text(
                json.dumps(receipt, ensure_ascii=False), encoding="utf-8"
            )

    def test_full_handoff_and_tamper_detection(self) -> None:
        stage_handoff.verify_planning(self.root, self.planning, self.state)
        self._create_writing_files()
        writing = self.root / "writing-handoff.json"
        writing_ticket = self.root / "writing-ticket.json"
        pipeline_guard.issue_ticket(self.state, "writing", writing_ticket)
        pipeline_guard.claim_ticket(self.state, "writing", writing_ticket)
        stage_handoff.create_writing(self.root, self.planning, writing, self.state)
        pipeline_guard.accept_handoff(self.state, "writing", writing_ticket, writing)
        stage_handoff.verify_writing(self.root, self.planning, writing, self.state)
        draft = self.root / "screenplay-drafts/episode-001.md"
        draft.write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(stage_handoff.HandoffError):
            stage_handoff.verify_writing(self.root, self.planning, writing, self.state)

    def test_planning_handoff_rejects_changed_topology(self) -> None:
        (self.root / "topology.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(stage_handoff.HandoffError):
            stage_handoff.verify_planning(self.root, self.planning, self.state)

    def test_validator_may_fill_character_introductions_without_invalidating_plan(self) -> None:
        (self.root / "character-introductions.json").write_text(
            json.dumps({"characters": [{"name": "测试人物"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        stage_handoff.verify_planning(self.root, self.planning, self.state)

    def test_planning_create_rejects_missing_artifact(self) -> None:
        (self.root / "emotional-spine.json").unlink()
        with self.assertRaises(stage_handoff.HandoffError):
            stage_handoff.create_planning(self.root, self.root / "new-planning.json", self.state)

    def test_handoff_rejects_path_escape(self) -> None:
        payload = json.loads(self.planning.read_text(encoding="utf-8"))
        payload["files"]["../../outside.txt"] = "0" * 64
        self.planning.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(stage_handoff.HandoffError):
            stage_handoff.verify_planning(self.root, self.planning, self.state)


if __name__ == "__main__":
    unittest.main()
