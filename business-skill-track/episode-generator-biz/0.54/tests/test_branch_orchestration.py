import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import decision_fissure_gate
import workflow_state
from validate_mainline_emotional_movement import CONTRACT_VERSION, validate
from validate_mainline_projection import canonical, sha


class BranchOrchestrationTests(unittest.TestCase):
    def test_state_machine_keeps_emotion_and_two_topologies_in_causal_order(self):
        names = [name for name, _action, _phase in workflow_state.FILE_STEPS]
        required = [
            "complete-story.json",
            "mainline-decomposition.json",
            "mainline-emotional-movement.json",
            "decision-fissure-audit.json",
            "story-treatment.json",
            "topology-draft-1.md",
            "topology.md",
            "mainline-path.json",
            "route-duration.json",
            "mainline-projection-review.json",
            "topology-review-a.json",
            "topology-review-b.json",
            "synopsis-set-review.json",
            "emotional-spine.json",
            "planning-acceptance.json",
        ]
        self.assertEqual([names.index(item) for item in required], sorted(names.index(item) for item in required))

    def test_story_derived_emotional_movement_is_required_before_fissures(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            story = {
                "contract_version": "nextplay.episode-complete-story.v1",
                "creative_brief_sha256": "a" * 64,
                "title": "测试故事",
                "complete_story": "林岑发现信号来自失踪的医疗船。她决定穿过风暴核实坐标，并在靠近后发现求救信号正在重复她母亲最后一次值班记录。",
            }
            decomposition = {
                "contract_version": "nextplay.mainline-decomposition.v1",
                "complete_story_sha256": sha(canonical(story)),
                "segments": [
                    {
                        "segment_id": "mainline-001",
                        "title": "信号",
                        "source_text": story["complete_story"],
                    }
                ],
            }
            movement = {
                "contract_version": CONTRACT_VERSION,
                "complete_story_sha256": sha(canonical(story)),
                "decomposition_sha256": hashlib.sha256(canonical(decomposition).encode("utf-8")).hexdigest(),
                "movements": [
                    {
                        "movement_id": "movement-001",
                        "segment_ids": ["mainline-001"],
                        "phase": "reversal",
                        "source_proof": "林岑发现信号来自失踪的医疗船",
                        "current": {"valence": -0.2, "arousal": 0.4, "dominance": -0.3},
                        "target": {"valence": 0.4, "arousal": 0.2, "dominance": 0.5},
                        "reality": {"valence": -0.6, "arousal": 0.8, "dominance": -0.7},
                        "pressure": "台风正在逼近医院",
                        "desired_state": "确认求救者身份",
                        "reality_shift": "私人记忆进入公共救援",
                        "control_change": "由观察转为主动靠近",
                        "unresolved_task": "决定是否冒险核实坐标",
                        "catalyst": "母亲值班记录迫使她立即核实",
                        "audience_known_risk": "观众知道风暴将切断医院退路",
                        "candidate_fissures": ["是否穿过风暴靠近医疗船"],
                    }
                ],
            }
            (root / "complete-story.json").write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
            (root / "mainline-decomposition.json").write_text(json.dumps(decomposition, ensure_ascii=False), encoding="utf-8")
            (root / "mainline-emotional-movement.json").write_text(json.dumps(movement, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(validate(root), [])
            movement["movements"][0]["segment_ids"] = ["mainline-999"]
            (root / "mainline-emotional-movement.json").write_text(json.dumps(movement, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("非法切片" in issue for issue in validate(root)))

    def test_fissure_contract_binds_pre_topology_emotion(self):
        self.assertIn("emotional_movement_sha256", decision_fissure_gate.ROOT_FIELDS)
        self.assertIn("emotional_movement_ids", decision_fissure_gate.FISSURE_FIELDS)

    def test_askuser_cannot_be_triggered_by_internal_node_math(self):
        text = (ROOT / "references" / "user-intent-lock.md").read_text(encoding="utf-8")
        self.assertIn("模型推导的最小节点数", text)
        self.assertIn("不能触发AskUser", text)


if __name__ == "__main__":
    unittest.main()
