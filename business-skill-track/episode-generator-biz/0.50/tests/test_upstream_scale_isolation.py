import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_creative_brief
import complete_story_gate
import validate_creative_brief
import validate_route_duration
import validate_topology
import validate_user_intent_lock


def write_intent(root: Path, *, fixed_episode_count=None, constraints=None) -> dict:
    request = "请保留我明确提出的内容。"
    (root / "user-request.md").write_text(request, encoding="utf-8")
    value = {
        "contract_version": "nextplay.user-intent-lock.v2",
        "source_sha256": hashlib.sha256(request.encode("utf-8")).hexdigest(),
        "resolution_status": "resolved",
        "fixed_episode_count": fixed_episode_count,
        "constraints": constraints or [],
        "conflicts": [],
        "resolutions": [],
    }
    (root / "user-intent-lock.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return value


class MinimalInputTests(unittest.TestCase):
    def test_external_output_is_limited_to_four_fixed_stage_phrases(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        boundary = (ROOT / "references" / "external-output-boundary.md").read_text(encoding="utf-8")
        phrases = ("正在生成故事", "正在生成分支", "正在生成剧本", "正在最终验收")
        for phrase in phrases:
            self.assertIn(phrase, skill)
            self.assertIn(f"`{phrase}`", boundary)
        self.assertIn("只能逐字发送", skill)
        self.assertIn("内部术语与产物一律不对用户暴露", skill)
        self.assertNotIn("建立情绪脊和完成完整故事", boundary)

    def test_builder_keeps_visible_volume_but_drops_hidden_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_intent(root)
            visible = {
                "title": "零度坐标",
                "logline": "一次求救信号迫使三个人重查旧案。",
                "story_description": "研究站收到十二年前沉船的求救信号。",
                "story_volume": "中篇",
                "node_count_hint": 45,
                "theme": "信任",
                "world_rules": ["隐藏规则"],
                "key_events": ["隐藏事件"],
                "ending_plan": {"total": 4},
                "assets": {
                    "characters": [{"name": "林岑", "description": "新任通信官", "current_motive": "隐藏动机"}],
                    "scenes": [{"name": "通信室", "description": "研究站通信空间", "story_function": "隐藏用途"}],
                    "props": [{"name": "求救坐标", "description": "十二年前的坐标", "state": "隐藏状态"}],
                },
            }
            path = root / "visible.json"
            path.write_text(json.dumps(visible, ensure_ascii=False), encoding="utf-8")
            brief = build_creative_brief.build(path, root)
            self.assertEqual(brief["story_volume"], "中篇")
            self.assertEqual(brief["assets"]["characters"], [{"name": "林岑", "description": "新任通信官"}])
            serialized = json.dumps(brief, ensure_ascii=False)
            for forbidden in ("node_count_hint", "theme", "world_rules", "key_events", "ending_plan", "current_motive", "story_function"):
                self.assertNotIn(forbidden, serialized)

    def test_fixed_episode_count_requires_explicit_user_statement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_intent(root, fixed_episode_count=12)
            _, _, issues = validate_user_intent_lock.validate_contract(root)
            self.assertTrue(any("缺少用户明确固定N集" in issue for issue in issues))

    def test_fixed_episode_count_is_checked_only_against_finished_topology(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            constraint = {
                "constraint_id": "user-001",
                "statement": "必须固定为2集",
                "scope": ["global"],
                "required": True,
                "forbidden_literals": [],
            }
            contract = write_intent(root, fixed_episode_count=2, constraints=[constraint])
            topology = """<!-- 拓扑合同：{\"contract_version\":\"nextplay.episode-topology.v1\",\"resolved_node_count\":1,\"count_source\":\"causal-expansion\"} -->
## episode-001 ｜ 唯一一集
- 后续节点：无
- 互动类型：主结局
- 结局：是
"""
            (root / "topology.md").write_text(topology, encoding="utf-8")
            episodes = root / "episodes"
            episodes.mkdir()
            episode_text = "这一集完整演出了故事并抵达结局。"
            (episodes / "episode-001.md").write_text(episode_text, encoding="utf-8")
            review = {
                "review_version": "nextplay.user-intent-review.v1",
                "source_sha256": contract["source_sha256"],
                "contract_sha256": validate_user_intent_lock.validate_contract(root)[1],
                "artifact_sha256": validate_user_intent_lock.artifact_digest(root),
                "constraints": [{
                    "constraint_id": "user-001",
                    "satisfied": True,
                    "explanation": "已按用户固定集数要求复核最终拓扑。",
                    "evidence": [{"location": "episode-001", "quote": "完整演出了故事"}],
                }],
                "issues": [],
            }
            (root / "user-intent-review.json").write_text(
                json.dumps(review, ensure_ascii=False), encoding="utf-8"
            )
            issues = validate_user_intent_lock.validate_user_intent_project(root)
            self.assertTrue(any("用户固定集数未满足" in issue for issue in issues))

    def test_complete_story_binds_directly_to_creative_brief(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_intent(root)
            brief = {
                "contract_version": "nextplay.episode-creative-brief.v1",
                "user_intent_contract_sha256": validate_user_intent_lock.validate_contract(root)[1],
                "title": "测试故事",
                "logline": None,
                "story_description": "一个人必须找到失踪的同伴。",
                "story_volume": "短篇",
                "assets": {"characters": [], "scenes": [], "props": []},
                "user_constraints": [],
            }
            (root / "creative-brief.json").write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
            validate_creative_brief.validate_frozen(root)
            story = {
                "contract_version": "nextplay.episode-complete-story.v1",
                "creative_brief_sha256": complete_story_gate.digest(brief),
                "title": "测试故事",
                "complete_story": "他在风暴前进入废弃站点寻找失踪同伴。" * 60,
            }
            (root / "complete-story.json").write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
            _, loaded = complete_story_gate.read_complete_story(root)
            self.assertEqual(loaded, story)


class NaturalScaleTests(unittest.TestCase):
    def test_four_ending_functions_do_not_require_padding_or_two_small_endings(self):
        def node(number, successors, interaction, ending=False, choices=None):
            return {
                "number": number,
                "title": f"节点{number}",
                "successors": successors,
                "choices": choices or [],
                "question": f"问题{number}" if choices else "",
                "interaction": interaction,
                "ending": ending,
            }

        nodes = {
            "episode-001": node(1, ["episode-002", "episode-003"], "选择", choices=[("继续", "episode-002"), ("离开", "episode-003")]),
            "episode-002": node(2, ["episode-004"], "剧情推进"),
            "episode-003": node(3, [], "小结局", True),
            "episode-004": node(4, ["episode-005", "episode-006"], "选择", choices=[("照原路", "episode-005"), ("改变策略", "episode-006")]),
            "episode-005": node(5, [], "主结局", True),
            "episode-006": node(6, ["episode-007", "episode-008"], "选择", choices=[("完成目标", "episode-007"), ("承担失败", "episode-008")]),
            "episode-007": node(7, [], "期望结局", True),
            "episode-008": node(8, [], "失败结局", True),
        }
        self.assertEqual(validate_topology.validate(nodes, 3, 1, 1, 1, 1), [])

        missing_small = {key: dict(value) for key, value in nodes.items() if key != "episode-003"}
        missing_small["episode-001"] = dict(nodes["episode-001"], successors=["episode-002"], choices=[] , interaction="剧情推进")
        self.assertTrue(any("缺少由故事线自然产生的小结局" in issue for issue in validate_topology.validate(missing_small)))

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
- 互动类型：主结局
- 结局：是
"""
            (root / "topology.md").write_text(topology, encoding="utf-8")
            accounting = {
                "contract_version": "nextplay.route-duration.v2",
                "unit": "minutes",
                "mainline_path": ["episode-001", "episode-002"],
                "node_minutes": {"episode-001": 60, "episode-002": 60},
                "paths": [{"ending_id": "episode-002", "node_ids": ["episode-001", "episode-002"], "total_minutes": 120}],
            }
            path = root / "route-duration.json"
            path.write_text(json.dumps(accounting), encoding="utf-8")
            self.assertEqual(validate_route_duration.validate(path, root / "topology.md"), [])


if __name__ == "__main__":
    unittest.main()
