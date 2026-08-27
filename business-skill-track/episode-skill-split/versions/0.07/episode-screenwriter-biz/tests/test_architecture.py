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
        self.assertIn("prose_dramatization", REQUIRED_CHECKS)

    def test_first_appearance_is_not_a_literal_anchor_search(self):
        source = (ROOT / "scripts" / "accept_node_screenplay.py").read_text(encoding="utf-8")
        self.assertNotIn("identity_anchor) or", source)
        quality = (ROOT / "references" / "dialogue-and-quality.md").read_text(encoding="utf-8")
        self.assertIn("不做`identity_anchor`原词搜索", quality)

    def test_dialogue_function_uses_exchange_not_every_line(self):
        quality = (ROOT / "references" / "dialogue-and-quality.md").read_text(encoding="utf-8")
        self.assertIn("以一个完整交流段而不是每句台词为功能单位", quality)
        self.assertNotIn("每句台词至少承担一项现场功能", quality)
        self.assertIn("补口语组织", quality)

    def test_branch_readiness_is_a_conditional_contract(self):
        source = (ROOT / "scripts" / "screenplay_contract.py").read_text(encoding="utf-8")
        self.assertIn('required_checks.add("choice_readiness")', source)
        self.assertIn("每个冻结选项提供不同正文证据", source)

    def test_manifest_inherits_006(self):
        manifest = json.loads((ROOT / "reference-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["based_on"], "episode-screenwriter-biz/0.06")
        self.assertEqual(manifest["skill_version"], "episode-screenwriter-biz/0.07")


if __name__ == "__main__":
    unittest.main()
