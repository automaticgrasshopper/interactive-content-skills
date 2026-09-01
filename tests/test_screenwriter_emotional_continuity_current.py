from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTE_SCRIPTS = ROOT / "business-skill-track/episode-skill-split/versions/0.08/episode-route-planner-biz/scripts"
SCREENWRITER_SCRIPTS = ROOT / "business-skill-track/episode-skill-split/versions/0.16/episode-screenwriter-biz/scripts"


def load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


route_contract = load_file("screenwriter_continuity_route_contract", ROUTE_SCRIPTS / "route_contract.py")
sys.path.insert(0, str(SCREENWRITER_SCRIPTS))
try:
    import episode_plan_index
    import build_enhancer_input
    import screenplay_contract
    import stage_contract
finally:
    sys.path.pop(0)


def accepted_route() -> dict:
    specs = [
        (
            "雨夜显影",
            [],
            ["episode-002"],
            {
                "单集梗概": "拆迁倒计时中，晚晴在暗房冲洗出一张异常照片，机械计时器迫使她立即判断照片里的危险是否真实。",
                "本集冲突": "晚晴必须在倒计时结束前判断照片是否足以改变自己的行动。",
                "entry_state": {"关系状态": "晚晴习惯独自判断风险"},
                "state_changes": {"照片状态": "异常细节已经显现"},
            },
            None,
        ),
        (
            "善意的第一步",
            ["episode-001"],
            ["episode-003"],
            {
                "单集梗概": "晚晴在雨巷找到照片中的顾客，周予安提醒她照片只是被遗忘的片段，她必须决定是否接受这次提醒。",
                "本集冲突": "晚晴既要继续核验照片，也要判断周予安的介入是阻碍还是善意。",
                "entry_state": {
                    "dramatic_pressure": {
                        "fact_trigger": "照片线索与周予安的提醒同时指向雨巷中的顾客。",
                        "felt_meaning": "晚晴把是否听取提醒理解为自己是否愿意让别人参与风险判断。",
                    }
                },
                "state_changes": {
                    "dramatic_effect": {
                        "resulting_action": "晚晴先让周予安说完，再共同核对照片。",
                        "human_change": "晚晴第一次不把周予安的介入直接视为阻碍。",
                        "later_effect": "后续面对不确定线索时，她会允许周予安先说明判断。",
                    }
                },
            },
            None,
        ),
        (
            "共同核验",
            ["episode-002"],
            [],
            {
                "单集梗概": "两人共同核验照片来源，在倒计时结束前确认顾客已经脱离危险，并保留继续调查的线索。",
                "本集冲突": "两人必须在证据不足时共同完成最后一次核验。",
                "entry_state": {"调查状态": "只剩一次核验机会"},
                "state_changes": {"调查状态": "顾客安全且线索被保留"},
            },
            "main",
        ),
    ]
    nodes = []
    for number, (title, predecessors, successors, material, ending_type) in enumerate(specs, start=1):
        node_id = f"episode-{number:03d}"
        nodes.append({
            "node_id": node_id,
            "node_type": "episode",
            "分集标题": title,
            "route_material": {
                **material,
                "allowed_characters": ["晚晴", "周予安"],
                "allowed_scenes": ["暗房", "雨巷"],
                "allowed_props": ["照片", "机械计时器"],
                "stop_boundary": "停在当前行动产生明确结果之后，不提前演出后续节点独占的核验与结算。",
            },
            "前置节点编号列表": predecessors,
            "后续节点编号列表": successors,
            "是否结局": ending_type is not None,
            "ending_type": ending_type,
            "互动节点": {
                "是否为分支节点": False,
                "是否有选择问题": False,
                "选择问题": "",
                "选项列表": [],
                "默认下一分集编号": successors[0] if successors else "无",
            },
            "node_route_material_hash": "",
        })
    edges, choices, endings = route_contract.expected_indexes(nodes)
    return route_contract.seal({
        "contract_version": route_contract.CONTRACT_VERSION,
        "capability_id": route_contract.CAPABILITY_ID,
        "project_id": "project-romance-task",
        "route_id": "route-romance-task",
        "route_version": "1",
        "route_status": "draft",
        "route_input_hash": "a" * 64,
        "route_output_hash": "",
        "accepted_at": None,
        "nodes": nodes,
        "edges": edges,
        "choices": choices,
        "endings": endings,
    }, "2026-09-01T00:00:00Z")


def node_context(route: dict, node_id: str, endings: list[dict] | None = None) -> dict:
    node = screenplay_contract.find_node(route, node_id)
    assert node is not None
    return {
        "contract_version": stage_contract.CONTEXT_VERSION,
        "project_id": route["project_id"],
        "route_id": route["route_id"],
        "route_version": route["route_version"],
        "route_output_hash": route["route_output_hash"],
        "node_id": node_id,
        "node_route_material_hash": node["node_route_material_hash"],
        "characters": [
            {
                "name": name,
                "public_identity": "修复旧照片的调查者" if name == "晚晴" else "协助核验线索的同事",
                "identity_anchor": "照片修复师" if name == "晚晴" else "调查搭档",
                "current_relevance": "正在处理当前照片线索",
                "relationship_context": "两人共同工作，晚晴尚不习惯让周予安介入自己的判断。",
            }
            for name in node["route_material"]["allowed_characters"]
        ],
        "scenes": [
            {"name": name, "public_description": "雨夜中的工作与调查场所。"}
            for name in node["route_material"]["allowed_scenes"]
        ],
        "props": [
            {"name": name, "public_description": "当前调查中已经登记并可见的物件。"}
            for name in node["route_material"]["allowed_props"]
        ],
        "direct_predecessor_endings": endings or [],
    }


def node_draft(route: dict, relationship_deltas: list[dict] | None = None) -> dict:
    node = screenplay_contract.find_node(route, "episode-001")
    assert node is not None
    script = (
        "【暗房·夜·内】\n\n"
        "机械计时器压着最后一分钟。晚晴夹起照片，异常人影在显影液中浮出来。\n\n"
        "周予安没有伸手抢照片，只把备用红灯推到晚晴手边。晚晴停了一瞬，把唯一的照片递到他面前，两人第一次并肩核对同一处裂痕。"
    )
    quote = "晚晴停了一瞬，把唯一的照片递到他面前"
    checks = [
        {"check": name, "passed": True, "evidence": [quote]}
        for name in sorted(screenplay_contract.REQUIRED_CHECKS)
    ]
    return {
        "contract_version": screenplay_contract.CONTRACT_VERSION,
        "capability_id": screenplay_contract.CAPABILITY_ID,
        "project_id": route["project_id"],
        "route_id": route["route_id"],
        "route_version": route["route_version"],
        "route_output_hash": route["route_output_hash"],
        "node_id": node["node_id"],
        "node_route_material_hash": node["node_route_material_hash"],
        "screenplay": {
            "分集剧本": {"完整剧本": script},
            "剧本创作分析": {
                "创作分析": "倒计时推动照片显影，同时用递出唯一照片的任务动作表现晚晴首次允许搭档共同判断。",
                "场景和段落展开计划": "先让异常影像形成压力，再以周予安克制介入和晚晴递出照片完成关系动作。",
                "连续性分析": "照片、计时器和人物位置连续，结尾只完成共同核对的起点。",
                "冷读与质量问题": "场景行动完整，关系含义来自任务动作，没有提前完成下一节点。",
                "验收结论": "PASS",
            },
            "关联角色": ["晚晴", "周予安"],
            "关联场景": ["暗房"],
            "关联道具": ["照片", "机械计时器"],
            "派生信息": {
                "character_deltas": [],
                "relationship_deltas": relationship_deltas if relationship_deltas is not None else [{
                    "source": "晚晴",
                    "target": "周予安",
                    "dimension": "trust",
                    "before": "不让周予安介入自己的风险判断",
                    "after": "愿意让周予安共同核对未确认线索",
                    "behavioral_effect": "以后遇到不确定照片时会先允许周予安说明判断",
                    "authority": "screenplay_observed",
                    "evidence": quote,
                }],
                "shared_memories": [],
            },
            "quality_checks": checks,
        },
        "screenplay_hash": "",
        "status": "draft",
        "accepted_at": None,
    }


class ScreenwriterEmotionalContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.route = accepted_route()
        self.index = episode_plan_index.build_index(self.route)

    def test_existing_route_material_becomes_small_lookahead_not_second_plan(self) -> None:
        navigation = episode_plan_index.navigation_slice(self.route, self.index, "episode-001")
        self.assertEqual(navigation["next_node_plans"][0]["node_id"], "episode-002")
        self.assertIn("第一次不把周予安", json.dumps(navigation, ensure_ascii=False))
        self.assertEqual(
            [item["node_id"] for item in navigation["graph_overview"]],
            ["episode-001", "episode-002", "episode-003"],
        )

    def test_accepted_delta_becomes_evidence_free_state_for_next_node(self) -> None:
        accepted = screenplay_contract.seal(
            self.route,
            node_draft(self.route),
            "2026-09-01T01:00:00Z",
            prior_state=screenplay_contract.empty_state_snapshot(),
        )
        derived = accepted["screenplay"]["派生信息"]
        self.assertIn("evidence", derived["relationship_deltas"][0])
        self.assertNotIn("evidence", derived["state_snapshot"]["relationships"][0])

        context = node_context(self.route, "episode-002", [{
            "node_id": "episode-001",
            "ending_excerpt": "两人并肩看向照片上的裂痕。",
            "state_snapshot": derived["state_snapshot"],
        }])
        packet = stage_contract.build_packet(self.route, context, "episode-002", self.index)
        payload = json.loads(packet.split("\n", 1)[1])
        self.assertEqual(
            payload["dramatic_state"]["relationships"][0]["current_state"],
            "愿意让周予安共同核对未确认线索",
        )
        self.assertNotIn("晚晴停了一瞬，把唯一的照片递到他面前", packet)

    def test_empty_changes_are_valid_and_do_not_force_emotion(self) -> None:
        draft = node_draft(self.route, relationship_deltas=[])
        self.assertEqual(screenplay_contract.validate(self.route, draft, require_accepted=False), [])
        accepted = screenplay_contract.seal(self.route, draft, "2026-09-01T01:00:00Z")
        self.assertEqual(accepted["screenplay"]["派生信息"]["state_snapshot"], screenplay_contract.empty_state_snapshot())

    def test_invalid_relation_or_unseen_evidence_is_rejected(self) -> None:
        draft = node_draft(self.route)
        delta = draft["screenplay"]["派生信息"]["relationship_deltas"][0]
        delta["target"] = "晚晴"
        delta["evidence"] = "正文中不存在的证明"
        issues = screenplay_contract.validate(self.route, draft, require_accepted=False)
        self.assertTrue(any("人物非法" in issue for issue in issues))
        self.assertTrue(any("证据不在正文" in issue for issue in issues))

    def test_merge_only_keeps_identical_branch_state(self) -> None:
        common = {
            "character": "晚晴",
            "axis": "strategy",
            "current_state": "遇到异常照片时先核对来源",
            "behavioral_effect": "不会仅凭第一眼判断采取行动",
            "source_node": "episode-001",
        }
        branch_a = screenplay_contract.empty_state_snapshot()
        branch_a["characters"].append(common)
        branch_b = copy.deepcopy(branch_a)
        branch_a["relationships"].append({
            "source": "晚晴", "target": "周予安", "dimension": "trust",
            "current_state": "愿意共同核对", "behavioral_effect": "先听完提醒", "source_node": "episode-002",
        })
        branch_b["relationships"].append({
            "source": "晚晴", "target": "周予安", "dimension": "trust",
            "current_state": "仍保持距离", "behavioral_effect": "只接受事实不接受判断", "source_node": "episode-003",
        })
        merged = stage_contract.common_state_snapshots([branch_a, branch_b])
        self.assertEqual(merged["characters"], [common])
        self.assertEqual(merged["relationships"], [])

    def test_cli_acceptance_binds_plan_index_and_writes_state_snapshot(self) -> None:
        context = node_context(self.route, "episode-001")
        packet = stage_contract.build_packet(self.route, context, "episode-001", self.index)
        draft = node_draft(self.route)
        script = draft["screenplay"]["分集剧本"]["完整剧本"]
        compact = script
        receipt = {
            "contract_version": stage_contract.RECEIPT_VERSION,
            "writing_packet_sha256": stage_contract.digest(packet),
            "compact_draft_sha256": stage_contract.digest(compact),
            "status": "PASS",
        }
        root = SCREENWRITER_SCRIPTS.parent
        enhancer_input = build_enhancer_input.build(
            packet,
            compact,
            receipt,
            (root / "references/full-scene-enhancer.md").read_text(encoding="utf-8"),
            (root / "references/dialogue-and-quality.md").read_text(encoding="utf-8"),
        )
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            values = {
                "route.json": self.route,
                "context.json": context,
                "index.json": self.index,
                "receipt.json": receipt,
                "draft.json": draft,
            }
            for name, value in values.items():
                (folder / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            texts = {
                "packet.txt": packet,
                "compact.md": compact,
                "enhancer.txt": enhancer_input,
                "screenplay.md": script,
            }
            for name, value in texts.items():
                (folder / name).write_text(value, encoding="utf-8")
            result = subprocess.run([
                sys.executable,
                str(SCREENWRITER_SCRIPTS / "accept_node_screenplay.py"),
                str(folder / "route.json"),
                str(folder / "context.json"),
                str(folder / "packet.txt"),
                str(folder / "compact.md"),
                str(folder / "receipt.json"),
                str(folder / "enhancer.txt"),
                str(folder / "screenplay.md"),
                str(folder / "draft.json"),
                str(folder / "patch.json"),
                "--plan-index",
                str(folder / "index.json"),
                "--accepted-at",
                "2026-09-01T01:00:00Z",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("NODE_SCREENPLAY_ACCEPTED", result.stdout.splitlines())
            patch = json.loads((folder / "patch.json").read_text(encoding="utf-8"))
            self.assertEqual(
                patch["screenplay"]["派生信息"]["state_snapshot"]["relationships"][0]["dimension"],
                "trust",
            )


if __name__ == "__main__":
    unittest.main()
