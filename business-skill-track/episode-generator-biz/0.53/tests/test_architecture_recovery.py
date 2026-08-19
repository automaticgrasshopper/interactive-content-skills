import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from dependency_binding import episode_dependency_sha256
from synopsis_set_gate import read_synopsis_set
from validate_character_appearances import identity_core


class StableBindingTests(unittest.TestCase):
    def test_receipt_metadata_does_not_change_episode_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            receipt = root / "planning-acceptance.json"
            base = {
                "content_leaves": {
                    "global": {"topology.md": "a" * 64},
                    "episodes": {"episode-001": "b" * 64},
                    "content_sha256": "c" * 64,
                },
                "files": {"review.json": "old"},
            }
            receipt.write_text(json.dumps(base), encoding="utf-8")
            before = episode_dependency_sha256(root, "episode-001")
            base["files"]["review.json"] = "new"
            receipt.write_text(json.dumps(base), encoding="utf-8")
            self.assertEqual(before, episode_dependency_sha256(root, "episode-001"))

    def test_internal_function_is_not_forced_into_first_appearance(self):
        self.assertEqual(identity_core("梁启荣", "酒店老板；旧案掩盖者与录音销毁计划策划者"), "酒店老板")


class SynopsisConflictTests(unittest.TestCase):
    def test_duplicate_generic_conflict_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "episode-synopses").mkdir()
            (root / "topology.md").write_text(
                """<!-- 拓扑合同：{\"contract_version\":\"nextplay.episode-topology.v1\",\"resolved_node_count\":2,\"count_source\":\"causal-expansion\"} -->\n## episode-001｜开端\n- 后续节点：episode-002\n- 互动类型：无\n- 选择问题：无\n- 结局：否\n\n## episode-002｜结局\n- 后续节点：无\n- 互动类型：无\n- 选择问题：无\n- 结局：是\n""",
                encoding="utf-8",
            )
            synopsis = "人物先面对明确处境和目标，随后采取具体行动，遭遇现场阻力后调整办法，最终造成可见结果并进入下一局面。" * 2
            for index, successors in ((1, ["episode-002"]), (2, [])):
                episode_id = f"episode-{index:03d}"
                payload = {
                    "contract_version": "nextplay.episode-synopsis.v1",
                    "episode_id": episode_id,
                    "title": "开端" if index == 1 else "结局",
                    "synopsis": synopsis,
                    "conflict": "人物必须面对当前阻力",
                    "predecessors": [] if index == 1 else ["episode-001"],
                    "successors": successors,
                }
                (root / "episode-synopses" / f"{episode_id}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "不得跨集复用"):
                read_synopsis_set(root)


if __name__ == "__main__":
    unittest.main()
