import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_episode_writing_input
import validate_emotional_topology
import validate_topology


def node(number, successors, *, choices=None, interaction="剧情", ending=False, title="节点"):
    return {
        "number": number,
        "title": f"{title}{number}",
        "successors": successors,
        "choices": choices or [],
        "question": "现在怎么办" if choices else "",
        "interaction": interaction,
        "ending": ending,
    }


class EmotionalArchitectureTests(unittest.TestCase):
    def test_topology_length_is_not_capped_by_interaction_density(self):
        nodes = {
            "episode-001": node(1, ["episode-002", "episode-003"], choices=[("离开", "episode-002"), ("继续", "episode-003")], interaction="选择"),
            "episode-002": node(2, [], interaction="小结局", ending=True),
            "episode-003": node(3, ["episode-004"]),
            "episode-004": node(4, ["episode-005"]),
            "episode-005": node(5, ["episode-006"]),
            "episode-006": node(6, ["episode-007"]),
            "episode-007": node(7, ["episode-008"]),
            "episode-008": node(8, ["episode-009", "episode-010"], choices=[("守住原路", "episode-009"), ("改变方案", "episode-010")], interaction="选择"),
            "episode-009": node(9, [], interaction="主结局", ending=True),
            "episode-010": node(10, ["episode-011", "episode-012"], choices=[("完成救援", "episode-011"), ("承担失败", "episode-012")], interaction="选择"),
            "episode-011": node(11, [], interaction="期望结局", ending=True),
            "episode-012": node(12, [], interaction="失败结局", ending=True),
        }
        self.assertEqual(validate_topology.validate(nodes), [])

    def test_flat_branch_cannot_pass_full_emotional_gate(self):
        nodes = {
            "episode-001": node(1, ["episode-002", "episode-003"], choices=[("行动甲", "episode-002"), ("行动乙", "episode-003")], interaction="选择"),
            "episode-002": node(2, [], interaction="主结局", ending=True),
            "episode-003": node(3, [], interaction="小结局", ending=True),
        }
        synopsis = "人物采取行动，承担不同后果，并完成当前路线的情绪任务。"
        spine = {
            "contract_version": validate_emotional_topology.SPINE_VERSION,
            "nodes": [
                {
                    "episode_id": episode_id,
                    "movement_ids": ["movement-001"],
                    "source_proof": synopsis,
                    "valence": 0.0 if episode_id == "episode-001" else 0.1,
                    "arousal": 0.0,
                    "dominance": 0.0,
                    "turn": episode_id != "episode-001",
                    "turn_reason": "行动造成路线状态发生明确改变" if episode_id != "episode-001" else "",
                    "turn_proof": synopsis if episode_id != "episode-001" else "",
                    "unresolved_task": "已完成当前路线任务" if episode_id != "episode-001" else "仍需决定行动方向",
                    "settlement": "resolved" if episode_id != "episode-001" else "open",
                }
                for episode_id in nodes
            ],
        }
        digest = hashlib.sha256(validate_emotional_topology.canonical_bytes(spine)).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            topology_path = root / "topology.md"
            spine_path = root / "emotional-spine.json"
            topology_path.write_text(f"<!-- 情绪脊校验：sha256:{digest} -->\n", encoding="utf-8")
            spine_path.write_text(json.dumps(spine, ensure_ascii=False), encoding="utf-8")
            with (
                patch.object(validate_emotional_topology, "parse", return_value=nodes),
                patch.object(validate_emotional_topology, "validate", return_value=[]),
                patch.object(validate_emotional_topology, "read_movement", return_value=(Path("movement"), {"movements": [{"movement_id": "movement-001"}]})),
                patch.object(validate_emotional_topology, "read_synopses", return_value={episode_id: synopsis for episode_id in nodes}),
            ):
                issues = validate_emotional_topology.validate_emotional_topology(
                    root, topology_path, spine_path, 1, 1, 0, 0, 1,
                )
        self.assertTrue(any("没有形成不同情绪方向" in issue for issue in issues))
        self.assertTrue(any("完整路线没有真实情绪拐点" in issue for issue in issues))

    def test_episode_writer_interface_rejects_emotional_process_material(self):
        terms = set(build_episode_writing_input.BANNED_TERMS)
        self.assertIn("情绪脊", terms)
        self.assertIn("拓扑", terms)
        adapter_source = (SCRIPTS / "build_episode_adaptation_source.py").read_text(encoding="utf-8")
        self.assertNotIn('"emotional_spine"', adapter_source)
        self.assertNotIn('"vad"', adapter_source.lower())


if __name__ == "__main__":
    unittest.main()
