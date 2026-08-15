import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_stage_two_input
import validate_emotional_movement
import validate_route_duration


class UpstreamScaleIsolationTests(unittest.TestCase):
    def test_stage_two_input_drops_upstream_duration_and_node_hint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            basis = {
                "story": {
                    "title": "测试故事",
                    "duration": "单次建议50分钟",
                    "node_count_hint": 20,
                    "core_goal": "完成目标",
                },
                "ending_plan": {"total": 1},
                "characters": [],
            }
            assets = {"characters": [], "scenes": [], "props": []}
            (root / "run-basis.json").write_text(json.dumps(basis), encoding="utf-8")
            (root / "asset-catalog.json").write_text(json.dumps(assets), encoding="utf-8")
            contract = {"constraints": []}

            def fake_load(path, _label):
                return basis if path.name == "run-basis.json" else assets

            with patch.object(
                build_stage_two_input,
                "validate_contract",
                return_value=(contract, "0" * 64, []),
            ), patch.object(build_stage_two_input, "load_object", side_effect=fake_load):
                packet = build_stage_two_input.from_sources(root)

            self.assertNotIn("duration", packet["story"])
            self.assertNotIn("node_count_hint", packet["story"])
            self.assertEqual(packet["story"]["core_goal"], "完成目标")

    def test_route_accounting_has_no_upstream_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            topology = """<!-- 拓扑合同：{\"contract_version\":\"nextplay.episode-topology.v1\",\"resolved_node_count\":2,\"count_source\":\"causal-expansion\"} -->
## episode-001 ｜ 起点
- 后续节点：episode-002
- 互动类型：无选择
- 结局：否
## episode-002 ｜ 结局
- 后续节点：无
- 互动类型：正式结局
- 结局：是
"""
            (root / "topology.md").write_text(topology, encoding="utf-8")
            accounting = {
                "contract_version": "nextplay.route-duration.v2",
                "unit": "minutes",
                "mainline_path": ["episode-001", "episode-002"],
                "node_minutes": {"episode-001": 60, "episode-002": 60},
                "paths": [
                    {
                        "ending_id": "episode-002",
                        "node_ids": ["episode-001", "episode-002"],
                        "total_minutes": 120,
                    }
                ],
            }
            (root / "route-duration.json").write_text(
                json.dumps(accounting), encoding="utf-8"
            )
            (root / "stage-two-input.json").write_text(
                json.dumps({"story": {"duration": "最多5分钟"}}), encoding="utf-8"
            )

            issues = validate_route_duration.validate(
                root / "route-duration.json",
                root / "topology.md",
                root / "stage-two-input.json",
            )
            self.assertEqual(issues, [])

    def test_emotional_movement_has_no_duration_field(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            movement = {
                "contract_version": "nextplay.unnumbered-emotional-movement.v1",
                "scale": {
                    "minimum_legal_path_length": 2,
                    "interaction_min": 1,
                    "interaction_max": 2,
                    "source": "causal-capacity",
                },
                "phases": [],
            }
            for name, value in zip(("起", "承", "转", "合"), range(4)):
                movement["phases"].append(
                    {
                        "phase": name,
                        "current": {"v": 0, "a": 0, "d": 0},
                        "target": {"v": 0.2, "a": 0.2, "d": 0.2},
                        "reality": {"v": -0.2, "a": 0.4, "d": -0.2},
                        "catalyst": f"足够清楚的催化事件{value}",
                        "audience_known_risk": f"足够清楚的已知风险{value}",
                        "candidate_fissures": [f"足够清楚的决定裂缝{value}"],
                    }
                )
            path = root / "movement.json"
            path.write_text(json.dumps(movement, ensure_ascii=False), encoding="utf-8")
            stage_two = root / "stage-two-input.json"
            stage_two.write_text(json.dumps({"story": {}}), encoding="utf-8")

            self.assertEqual(
                validate_emotional_movement.validate(path, stage_two), []
            )


if __name__ == "__main__":
    unittest.main()
