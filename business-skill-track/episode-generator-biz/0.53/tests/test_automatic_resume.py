import sys
import hashlib
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_state
import workflow_state

TOPOLOGY = """<!-- 拓扑合同：{\"contract_version\":\"nextplay.episode-topology.v1\",\"resolved_node_count\":2,\"count_source\":\"causal-expansion\"} -->
## episode-001｜开端
- 后续节点：episode-002
- 互动类型：无
- 选择问题：无
- 结局：否

## episode-002｜结局
- 后续节点：无
- 互动类型：无
- 选择问题：无
- 结局：是
"""


def state(first: str = "QUEUED", second: str = "QUEUED") -> dict:
    return {
        "contract_version": run_state.VERSION,
        "episode_order": ["episode-001", "episode-002"],
        "episodes": {
            "episode-001": {"state": first, "leases": {}},
            "episode-002": {"state": second, "leases": {}},
        },
    }


class AutomaticResumeTests(unittest.TestCase):
    def test_every_pre_episode_cut_has_one_current_task_action(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(workflow_state, "artifact_issues", return_value=[]):
                for filename, expected, _phase in workflow_state.FILE_STEPS:
                    value = workflow_state.status(root)
                    self.assertEqual(value["status"], "IN_PROGRESS")
                    self.assertEqual(len(value["next_actions"]), 1)
                    self.assertEqual(value["next_actions"][0]["action"], expected)
                    self.assertEqual(value["next_actions"][0]["execution_mode"], "current_task")
                    path = root / filename
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}" if path.suffix == ".json" else "ready", encoding="utf-8")
                    if filename == "synopsis-set-review.json":
                        directory = root / "episode-synopses"
                        directory.mkdir(exist_ok=True)
                        (directory / "episode-001.json").write_text("{}", encoding="utf-8")
                    if filename == "character-introductions.json":
                        break

    def test_existing_invalid_checkpoint_returns_to_earliest_step(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "user-request.md").write_text("有效用户要求", encoding="utf-8")
            (root / "user-intent-lock.json").write_text("{}", encoding="utf-8")
            value = workflow_state.status(root)
        self.assertEqual(value["status"], "IN_PROGRESS")
        self.assertEqual(value["reason_code"], "CHECKPOINT_INVALID")
        self.assertEqual(value["next_actions"][0]["action"], "BUILD_USER_INTENT_LOCK")

    def test_episode_status_returns_exact_next_action(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "topology.md").write_text(TOPOLOGY, encoding="utf-8")
            value = state(first="COMPACT_DRAFT_VALIDATED")
            with patch.object(run_state, "load", return_value=value), patch.object(run_state, "require_current_planning"):
                current = run_state.status(root)
            self.assertEqual(current["status"], "IN_PROGRESS")
            self.assertEqual(current["next_actions"][0]["action"], "ENHANCE")
            self.assertEqual(current["next_actions"][0]["execution_mode"], "current_task")
            self.assertTrue(current["next_actions"][0]["standard_input"].endswith("enhancer-inputs/episode-001.txt"))

    def test_context_cut_resumes_live_lease_and_recovers_expired_lease(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "topology.md").write_text(TOPOLOGY, encoding="utf-8")
            live = state(first="ADAPTED")
            live["episodes"]["episode-001"]["leases"] = {
                "WRITE_COMPACT_DRAFT": {"lease": "live", "expires_at": run_state.iso(run_state.now() + timedelta(minutes=5))}
            }
            with patch.object(run_state, "load", return_value=live), patch.object(run_state, "require_current_planning"):
                self.assertTrue(run_state.status(root)["next_actions"][0]["resume"])
            expired = state(first="ADAPTED")
            expired["episodes"]["episode-001"]["leases"] = {
                "WRITE_COMPACT_DRAFT": {"lease": "old", "expires_at": run_state.iso(run_state.now() - timedelta(minutes=5))}
            }
            with patch.object(run_state, "load", return_value=expired), patch.object(run_state, "require_current_planning"):
                item = run_state.status(root)["next_actions"][0]
            self.assertEqual(item["action"], "RECOVER_EXPIRED_LEASE")

    def test_delivery_completion_is_hash_bound_not_file_presence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = {
                "business_output_sha256": root / "business-output.json",
                "completion_receipt_sha256": root / "completion-receipt.json",
                "handoff_sha256": root / "episode-handoff.json",
            }
            for path in paths.values():
                path.write_text("current", encoding="utf-8")
            receipt = {
                "contract_version": workflow_state.DELIVERY_VERSION,
                "status": "PASS",
                **{field: hashlib.sha256(path.read_bytes()).hexdigest() for field, path in paths.items()},
            }
            (root / "delivery-accepted.json").write_text(json.dumps(receipt), encoding="utf-8")
            self.assertTrue(workflow_state.delivery_is_current(root))
            (root / "business-output.json").write_text("changed", encoding="utf-8")
            self.assertFalse(workflow_state.delivery_is_current(root))


if __name__ == "__main__":
    unittest.main()
