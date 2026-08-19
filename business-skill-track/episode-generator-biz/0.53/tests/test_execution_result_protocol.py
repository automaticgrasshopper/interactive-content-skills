import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_state
import workflow_state
import complete_story_gate


class ExecutionResultProtocolTests(unittest.TestCase):
    def test_handled_validation_failure_exits_zero_with_one_recovery_action(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing-topology.md"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_topology.py"), str(missing)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["status"], "IN_PROGRESS")
        self.assertEqual(value["next_action"]["action"], "REBUILD_TOPOLOGY")
        self.assertNotIn("WAITING_USER", result.stdout)

    def test_handled_failure_is_resumable_after_context_cut(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            visible = root / "visible.json"
            visible.write_text("{}", encoding="utf-8")
            first = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build_creative_brief.py"),
                    str(visible),
                    str(root),
                    "--output",
                    str(root / "creative-brief.json"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue((root / ".execution-state.json").is_file())
            resumed = workflow_state.status(root)
        self.assertEqual(resumed["status"], "IN_PROGRESS")
        self.assertEqual(len(resumed["next_actions"]), 1)
        self.assertEqual(resumed["next_actions"][0]["action"], "REBUILD_CREATIVE_BRIEF")

    def test_only_verified_user_constraint_conflict_waits_for_user(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = "固定为6集，同时固定为8集"
            (root / "user-request.md").write_text(request, encoding="utf-8")
            contract = {
                "contract_version": "nextplay.user-intent-lock.v2",
                "source_sha256": hashlib.sha256(request.encode()).hexdigest(),
                "resolution_status": "needs-user",
                "fixed_episode_count": None,
                "constraints": [
                    {"constraint_id": "user-001", "statement": "固定为6集", "scope": ["global"], "required": True, "forbidden_literals": []},
                    {"constraint_id": "user-002", "statement": "固定为8集", "scope": ["global"], "required": True, "forbidden_literals": []},
                ],
                "conflicts": [{
                    "conflict_id": "conflict-001",
                    "constraint_ids": ["user-001", "user-002"],
                    "question": "最终固定为几集？",
                    "options": ["固定为6集", "固定为8集"],
                }],
                "resolutions": [],
            }
            (root / "user-intent-lock.json").write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
            value = workflow_state.status(root)
        self.assertEqual(value["status"], "WAITING_USER")
        self.assertEqual(value["reason_code"], "USER_CONSTRAINT_CONFLICT")

    def test_content_failure_rolls_back_to_full_regeneration_edge(self):
        state = {
            "episodes": {
                "episode-001": {
                    "state": "ENHANCED",
                    "leases": {"VALIDATE_STRUCTURE": {"lease": "token"}},
                    "outputs": {
                        "ADAPT": {},
                        "WRITE_COMPACT_DRAFT": {},
                        "VALIDATE_COMPACT_DRAFT": {},
                        "ENHANCE": {},
                    },
                    "content_failures": {},
                }
            }
        }
        with patch.object(run_state, "load", return_value=state), patch.object(run_state, "atomic_write"):
            run_state.fail(Path("/tmp/cache"), "episode-001", "VALIDATE_STRUCTURE", "token", "人物首次出场身份缺失", "content")
        episode = state["episodes"]["episode-001"]
        self.assertEqual(episode["state"], "COMPACT_DRAFT_VALIDATED")
        self.assertNotIn("ENHANCE", episode["outputs"])

    def test_retry_exhaustion_stops_without_asking_user(self):
        state = {
            "episode_order": ["episode-001"],
            "episodes": {
                "episode-001": {
                    "state": "ADAPTED",
                    "content_failures": {"WRITE_COMPACT_DRAFT": run_state.MAX_CONTENT_ATTEMPTS},
                }
            },
        }
        with patch.object(run_state, "load", return_value=state), patch.object(run_state, "require_current_planning"):
            value = run_state.status(Path("/tmp/cache"))
        self.assertEqual(value["status"], "STOPPED")
        self.assertEqual(value["next_actions"], [])

    def test_validators_cannot_emit_waiting_user(self):
        allowed = {"workflow_state.py", "execution_result.py"}
        offenders = []
        for path in SCRIPTS.glob("*.py"):
            if path.name not in allowed and "WAITING_USER" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_production_scripts_do_not_return_process_error_codes(self):
        offenders = []
        for path in SCRIPTS.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "return 1" in text or "return 2" in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_volume_signal_never_creates_user_recommendation(self):
        proof = "主角在连续行动和后果中完成了最终结算。"
        packet = {
            "complete_story_sha256": "story",
            "creative_brief_sha256": "brief",
            "story_volume_signal": "短篇",
            "user_constraints": [],
            "complete_story": {"complete_story": proof},
        }
        review = {
            "complete_story_sha256": "story",
            "creative_brief_sha256": "brief",
            "covered_checks": list(complete_story_gate.REQUIRED_CHECKS),
            "evidence": [
                {"check": check, "proof": proof, "explanation": "该证据能够证明当前检查已经满足。"}
                for check in complete_story_gate.REQUIRED_CHECKS
            ],
            "volume_assessment": {
                "result": "story-longer-than-signal",
                "reason": "故事自然因果链明显长于普通体量信号。",
                "recommendation": None,
            },
            "issues": [],
        }
        self.assertEqual(complete_story_gate.validate_review(packet, review), [])
        review["volume_assessment"]["recommendation"] = "请用户选择改故事还是改体量"
        self.assertTrue(any("不得制造" in issue for issue in complete_story_gate.validate_review(packet, review)))


if __name__ == "__main__":
    unittest.main()
