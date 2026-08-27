from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_enhancer_input import build as build_enhancer_input
from screenplay_contract import REQUIRED_CHECKS
from stage_contract import CONTEXT_VERSION, PACKET_VERSION, RECEIPT_VERSION, context_issues, digest
from validate_compact_draft import validate as validate_compact_draft


def route() -> dict:
    return {
        "project_id": "p",
        "route_id": "r",
        "route_version": "1",
        "route_output_hash": "route-hash",
        "nodes": [{
            "node_id": "episode-001",
            "node_route_material_hash": "node-hash",
            "route_material": {
                "allowed_characters": ["沈葵"],
                "allowed_scenes": ["县融媒体办公室"],
                "allowed_props": ["匿名检测报告"],
            },
            "前置节点编号列表": [],
        }],
    }


def context() -> dict:
    return {
        "contract_version": CONTEXT_VERSION,
        "project_id": "p",
        "route_id": "r",
        "route_version": "1",
        "route_output_hash": "route-hash",
        "node_id": "episode-001",
        "node_route_material_hash": "node-hash",
        "characters": [{
            "name": "沈葵",
            "public_identity": "县融媒体中心记者",
            "identity_anchor": "记者",
            "current_relevance": "收到老桥匿名检测报告并负责第一轮事实核验",
        }],
        "scenes": [{"name": "县融媒体办公室", "public_description": "县融媒体中心夜间值班办公室"}],
        "props": [{"name": "匿名检测报告", "public_description": "没有署名、指向老桥加固数据问题的纸质报告"}],
        "direct_predecessor_endings": [],
    }


class ArchitectureTests(unittest.TestCase):
    def test_context_rejects_name_without_identity(self):
        value = context()
        value["characters"][0]["public_identity"] = ""
        self.assertTrue(any("公开身份" in issue for issue in context_issues(route(), value, "episode-001")))

    def test_context_rejects_missing_identity_anchor(self):
        value = context()
        value["characters"][0]["identity_anchor"] = ""
        self.assertTrue(any("公开身份" in issue for issue in context_issues(route(), value, "episode-001")))

    def test_packet_includes_current_branch_contract(self):
        source = (ROOT / "scripts" / "stage_contract.py").read_text(encoding="utf-8")
        self.assertIn('"branch_contract": node.get("互动节点")', source)

    def test_compact_draft_has_no_length_or_dialogue_quota(self):
        packet = f"WRITING_PACKET_VERSION={PACKET_VERSION}\n{{}}\n"
        draft = "【县融媒体办公室·雨夜·内】\n\n沈葵把匿名检测报告压在桌上，翻到没有署名的一页。"
        self.assertEqual(validate_compact_draft(packet, draft), [])

    def test_compact_draft_rejects_production_meta_language(self):
        packet = f"WRITING_PACKET_VERSION={PACKET_VERSION}\n{{}}\n"
        draft = "【县融媒体办公室·雨夜·内】\n\n本节点停在停止边界。"
        self.assertTrue(any("制作元话语" in issue for issue in validate_compact_draft(packet, draft)))

    def test_enhancer_input_binds_packet_draft_and_references(self):
        packet = f"WRITING_PACKET_VERSION={PACKET_VERSION}\n{{}}\n"
        draft = "【办公室·夜·内】\n\n沈葵翻开报告。"
        receipt = {
            "contract_version": RECEIPT_VERSION,
            "writing_packet_sha256": digest(packet),
            "compact_draft_sha256": digest(draft),
            "status": "PASS",
        }
        value = build_enhancer_input(packet, draft, receipt, "enhancer", "quality")
        self.assertIn(f"WRITING_PACKET_SHA256={digest(packet)}", value)
        self.assertTrue(value.rstrip().endswith(draft))

    def test_final_checks_cover_first_appearance_and_prose(self):
        self.assertIn("first_appearance", REQUIRED_CHECKS)
        self.assertIn("spatial_continuity", REQUIRED_CHECKS)
        self.assertIn("prose_dramatization", REQUIRED_CHECKS)

    def test_first_appearance_is_not_a_literal_anchor_search(self):
        source = (ROOT / "scripts" / "accept_node_screenplay.py").read_text(encoding="utf-8")
        self.assertNotIn("identity_anchor) or", source)
        review = (ROOT / "references" / "node-screenwriting.md").read_text(encoding="utf-8")
        self.assertIn("不要求`identity_anchor`原词出现", review)

    def test_dialogue_function_uses_exchange_not_every_line(self):
        quality = (ROOT / "references" / "dialogue-and-quality.md").read_text(encoding="utf-8")
        self.assertIn("以一个完整交流段而不是每句台词为功能单位", quality)
        self.assertNotIn("每句台词至少承担一项现场功能", quality)
        self.assertIn("补口语组织", quality)

    def test_branch_readiness_is_a_conditional_contract(self):
        source = (ROOT / "scripts" / "screenplay_contract.py").read_text(encoding="utf-8")
        self.assertIn('required_checks.add("choice_readiness")', source)
        self.assertIn("每个冻结选项提供不同正文证据", source)

    def test_spatial_continuity_requires_causal_blocking_not_action_filler(self):
        enhancer = (ROOT / "references" / "full-scene-enhancer.md").read_text(encoding="utf-8")
        self.assertIn("空间连续是防错，不是扩写任务", enhancer)
        self.assertIn("不记录没有后续作用的走路", enhancer)
        self.assertIn("不组织人物摆成“终场画面”", enhancer)

    def test_each_writing_concern_has_one_owner(self):
        compact = (ROOT / "references" / "compact-action-draft.md").read_text(encoding="utf-8")
        dialogue = (ROOT / "references" / "dialogue-and-quality.md").read_text(encoding="utf-8")
        review = (ROOT / "references" / "node-screenwriting.md").read_text(encoding="utf-8")
        self.assertIn("本阶段只决定戏剧拍", compact)
        self.assertNotIn("identity_anchor", compact)
        self.assertIn("本文件只管对白", dialogue)
        self.assertNotIn("首次出场", dialogue)
        self.assertIn("本阶段只判定正式剧本能否交付", review)
        self.assertIn("不在正文里逐项补证明", review)

    def test_pacing_advances_by_dramatic_change(self):
        compact = (ROOT / "references" / "compact-action-draft.md").read_text(encoding="utf-8")
        enhancer = (ROOT / "references" / "full-scene-enhancer.md").read_text(encoding="utf-8")
        self.assertIn("一个戏剧拍必须至少带来一种新变化", compact)
        self.assertIn("写作者拥有全部表达权，但没有新增戏剧拍的权力", enhancer)
        self.assertIn("每个戏剧拍只演一次", enhancer)

    def test_user_progress_is_plain_language_and_not_persisted(self):
        progress = (ROOT / "references" / "user-visible-progress.md").read_text(encoding="utf-8")
        for line in ("正在撰写初稿", "正在进行润色", "正在对照细节", "正在完成终稿", "正在合并剧本"):
            self.assertIn(line, progress)
        interface = (ROOT / "references" / "business-interface.md").read_text(encoding="utf-8")
        self.assertIn("阶段播报是临时展示文本", interface)
        self.assertIn("不得写入路线、节点补丁、剧本正文或创作分析", interface)

    def test_enhancer_requires_formal_scene_heading(self):
        enhancer = (ROOT / "references" / "full-scene-enhancer.md").read_text(encoding="utf-8")
        self.assertIn("正文必须以`【场景·时段·内/外】`格式", enhancer)

    def test_manifest_inherits_009(self):
        manifest = json.loads((ROOT / "reference-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["based_on"], "episode-screenwriter-biz/0.09")
        self.assertEqual(manifest["skill_version"], "episode-screenwriter-biz/0.10")
        self.assertEqual(manifest["release_status"], "active")

    def test_active_pointer_selects_010_without_changing_route_skill(self):
        ownership = json.loads((ROOT.parents[2] / "field-ownership.json").read_text(encoding="utf-8"))
        self.assertEqual(ownership["route_skill"], "episode-route-planner-biz/0.01")
        self.assertEqual(ownership["screenplay_skill"], "episode-screenwriter-biz/0.10")


if __name__ == "__main__":
    unittest.main()
