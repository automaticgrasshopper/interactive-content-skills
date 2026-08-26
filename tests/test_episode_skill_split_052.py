from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLIT = ROOT / "business-skill-track" / "episode-skill-split"
VERSION = SPLIT / "versions" / "0.01"
ROUTE_SKILL = VERSION / "episode-route-planner-biz"
SCRIPT_SKILL = VERSION / "episode-screenwriter-biz"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


route_contract = load_module("split_route_contract", ROUTE_SKILL / "scripts" / "route_contract.py")
planning_gate = load_module("split_planning_gate", ROUTE_SKILL / "scripts" / "planning_gate.py")
workflow_state = load_module("split_workflow_state", ROUTE_SKILL / "scripts" / "workflow_state.py")
screenplay_contract = load_module("split_screenplay_contract", SCRIPT_SKILL / "scripts" / "screenplay_contract.py")


def candidate_route() -> dict:
    node_specs = [
        ("入口抉择", ["episode-002", "episode-003", "episode-004", "episode-005"], None),
        ("守住原案", [], "main"),
        ("公开真相", [], "expected"),
        ("证据失效", [], "failure"),
        ("主动离场", [], "small"),
    ]
    nodes = []
    for index, (title, successors, ending_type) in enumerate(node_specs, start=1):
        node_id = f"episode-{index:03d}"
        options = []
        if successors:
            labels = ["坚持原方案", "公开全部证据", "冒险提前验证", "放弃调查离开"]
            options = [
                {"选项编号": str(number), "选项文字": label, "目标分集编号": target}
                for number, (label, target) in enumerate(zip(labels, successors), start=1)
            ]
        predecessors = [] if index == 1 else ["episode-001"]
        nodes.append({
            "node_id": node_id,
            "node_type": "episode",
            "分集标题": title,
            "route_material": {
                "单集梗概": f"沈砚在控制室面对第{index}轮压力，采取明确行动，现场反馈改变证据与关系状态，并把路线推向本节点的真实结果。",
                "本集冲突": f"沈砚必须在不断收紧的现场条件下完成第{index}轮行动并承担结果。",
                "entry_state": {"证据": "待核验", "关系": "合作仍有裂痕"},
                "state_changes": {"证据": "已形成当前路线结果", "关系": "因行动发生变化"},
                "allowed_characters": ["沈砚", "顾川"],
                "allowed_scenes": ["控制室"],
                "allowed_props": ["证据盒"],
                "stop_boundary": "停在当前行动的可见结果落地之后，不提前演出任何后续节点的独占核验与结算。",
            },
            "前置节点编号列表": predecessors,
            "后续节点编号列表": successors,
            "是否结局": ending_type is not None,
            "ending_type": ending_type,
            "互动节点": {
                "是否为分支节点": bool(successors),
                "是否有选择问题": bool(successors),
                "选择问题": "证据只够支持一次行动，沈砚现在怎么做？" if successors else "",
                "选项列表": options,
                "默认下一分集编号": successors[0] if successors else "无",
            },
            "node_route_material_hash": "",
        })
    edges, choices, endings = route_contract.expected_indexes(nodes)
    return {
        "contract_version": route_contract.CONTRACT_VERSION,
        "capability_id": route_contract.CAPABILITY_ID,
        "skill_version": route_contract.SKILL_VERSION,
        "project_id": "project-demo",
        "route_id": "route-demo",
        "route_version": "1",
        "route_status": "draft",
        "route_input_hash": hashlib.sha256("visible-plan-and-text-assets".encode()).hexdigest(),
        "route_output_hash": "",
        "accepted_at": None,
        "nodes": nodes,
        "edges": edges,
        "choices": choices,
        "endings": endings,
    }


def planning_evidence(route: dict) -> dict:
    first = (
        "沈砚在控制室守着唯一的证据盒，警报逼近，她必须决定坚持原方案、公开证据、提前验证，还是永久离开调查。"
        "每个动作都会改变证据、关系和核心目标，不能只用不同说法回到相同结果。"
    )
    second = (
        "沈砚最终守住原案，把证据送到正式核验位置；她承担关系裂痕并完成冻结故事的自然主线结算。"
        "顾川确认这次行动留下了不可逆的事实结果。"
    )
    quote = "沈砚在控制室守着唯一的证据盒"
    reviews = []
    checks_by_pass = {
        "A": planning_gate.REVIEW_CHECKS["A"],
        "B": planning_gate.REVIEW_CHECKS["B"],
    }
    for review_pass, names in checks_by_pass.items():
        reviews.append({
            "review_pass": review_pass,
            "verdict": "PASS",
            "checks": [
                {
                    "check": name,
                    "passed": True,
                    "explanation": "当前封闭材料中的逐字事实能够支持本项判断。",
                    "evidence_quote": quote,
                }
                for name in names
            ],
            "issues": [],
        })
    evidence = {
        "contract_version": planning_gate.CONTRACT_VERSION,
        "project_id": route["project_id"],
        "route_id": route["route_id"],
        "route_version": route["route_version"],
        "route_input_hash": route["route_input_hash"],
        "route_candidate_hash": planning_gate.digest(route),
        "complete_story": {
            "contract_version": "nextplay.episode-complete-story.v1",
            "title": "证据盒",
            "complete_story": first + second,
        },
        "mainline_segments": [
            {"segment_id": "mainline-001", "source_text": first, "route_node_id": "episode-001"},
            {"segment_id": "mainline-002", "source_text": second, "route_node_id": "episode-002"},
        ],
        "emotional_movements": [
            {
                "movement_id": "movement-001",
                "segment_ids": ["mainline-001"],
                "source_proof": quote,
                "pressure": "警报逼近且证据只能支持一次行动",
                "desired_state": "保住证据并完成正式核验",
                "reality_shift": "四项互斥动作同时成为现实选择",
                "control_change": "沈砚从被动等待转为掌握决定权",
                "unresolved_task": "仍需选择唯一行动并承担结果",
                "candidate_fissures": ["现在采用哪一种证据行动"],
            },
            {
                "movement_id": "movement-002",
                "segment_ids": ["mainline-002"],
                "source_proof": "沈砚最终守住原案",
                "pressure": "关系裂痕仍需由行动结果结算",
                "desired_state": "让正式核验取得可信证据",
                "reality_shift": "原案被送达并成为不可逆事实",
                "control_change": "沈砚承担代价后重新取得控制",
                "unresolved_task": "主线任务已经完成并等待结算",
                "candidate_fissures": [],
            },
        ],
        "decision_fissures": [
            {
                "fissure_id": "fissure-001",
                "source_node_id": "episode-001",
                "mainline_position_proof": quote,
                "emotional_movement_ids": ["movement-001"],
                "decision_question": "证据只够支持一次行动，沈砚现在怎么做？",
                "actions": [
                    {
                        "option_text": "坚持原方案", "target_node_id": "episode-002",
                        "immediate_consequence": "证据进入正式核验但关系裂痕被保留下来。",
                        "persistent_differences": {"证据": "正式核验", "关系": "仍有裂痕"},
                        "core_goal_status": "achieved", "consumed_at_node_ids": [],
                    },
                    {
                        "option_text": "公开全部证据", "target_node_id": "episode-003",
                        "immediate_consequence": "证据取得公众见证并迫使系统公开回应。",
                        "persistent_differences": {"证据": "公开见证", "关系": "公众加入"},
                        "core_goal_status": "achieved", "consumed_at_node_ids": [],
                    },
                    {
                        "option_text": "冒险提前验证", "target_node_id": "episode-004",
                        "immediate_consequence": "提前验证烧毁备份并使核心核验彻底失败。",
                        "persistent_differences": {"证据": "备份失效", "关系": "合作破裂"},
                        "core_goal_status": "failed", "consumed_at_node_ids": [],
                    },
                    {
                        "option_text": "放弃调查离开", "target_node_id": "episode-005",
                        "immediate_consequence": "沈砚永久退出调查并失去再次核验证据的机会。",
                        "persistent_differences": {"证据": "永久放弃", "关系": "退出合作"},
                        "core_goal_status": "abandoned", "consumed_at_node_ids": [],
                    },
                ],
                "merge_node_id": None,
                "merge_common_fact": "",
            }
        ],
        "topology_draft_1": {
            "entry_node_id": "draft-001",
            "nodes": [
                {"node_id": "draft-001", "kind": "story", "ending_type": None, "successors": ["draft-002"]},
                {"node_id": "draft-002", "kind": "choice", "ending_type": None, "successors": ["draft-003", "draft-004", "draft-005", "draft-006"]},
                {"node_id": "draft-003", "kind": "ending", "ending_type": "main", "successors": []},
                {"node_id": "draft-004", "kind": "ending", "ending_type": "expected", "successors": []},
                {"node_id": "draft-005", "kind": "ending", "ending_type": "failure", "successors": []},
                {"node_id": "draft-006", "kind": "ending", "ending_type": "small", "successors": []},
            ],
        },
        "emotional_spine": [
            {
                "node_id": node["node_id"], "valence": -0.4 + index * 0.2,
                "arousal": 0.7, "dominance": -0.3 + index * 0.15,
                "turn": index == 0, "turn_reason": "互斥行动第一次成为可执行决定" if index == 0 else "",
                "source_quote": "沈砚在控制室",
            }
            for index, node in enumerate(route["nodes"])
        ],
        "reviews": reviews,
    }
    evidence["story_treatment"] = {
        "contract_version": "nextplay.episode-story-treatment.v5",
        "title": "证据盒",
        "complete_story": "冻结主线在入口裂缝生长出三条主要结算路线和一条永久离场路线。",
        "choices": [
            {
                "choice_id": "choice-001",
                "dramatic_cause": "证据只够支持一次不可撤销的行动，沈砚必须立即决定如何使用。",
                "question": "证据只够支持一次行动，沈砚现在怎么做？",
                "options": [
                    {
                        "option_id": str(index),
                        "option_text": action["option_text"],
                        "immediate_consequence": action["immediate_consequence"],
                        "lasting_difference": "；".join(f"{key}变为{value}" for key, value in action["persistent_differences"].items()),
                    }
                    for index, action in enumerate(evidence["decision_fissures"][0]["actions"], start=1)
                ],
                "merge_or_ending": "四项行动分别进入主结局、期望结局、失败结局和永久离场的小结局。",
            }
        ],
        "endings": [
            {"title": "守住原案", "kind": "main", "causal_payoff": "原方案进入正式核验并完成冻结故事的自然结算。"},
            {"title": "公开真相", "kind": "expected", "causal_payoff": "公开见证迫使系统回应并最充分兑现查明真相的目标。"},
            {"title": "证据失效", "kind": "failure", "causal_payoff": "提前验证烧毁备份，使核心核验推进到验证时彻底失败。"},
        ],
        "small_endings": [
            {"title": "主动离场", "kind": "small", "source_action_id": "action-004", "causal_payoff": "沈砚永久退出调查，不再具有返回核心故事的行动基础。"}
        ],
    }
    return evidence


def recursive_branch_route() -> dict:
    route = candidate_route()
    specs = [
        ("入口抉择", [], ["episode-002", "episode-003", "episode-004"], None, "入口行动怎么选？", ["守住原案", "继续追查", "退出调查"]),
        ("守住原案", ["episode-001"], [], "main", "", []),
        ("公开线索", ["episode-001"], ["episode-005", "episode-006"], None, "公开线索后还要怎么推进？", ["请求公众见证", "冒险进入后台"]),
        ("主动离场", ["episode-001"], [], "small", "", []),
        ("公开真相", ["episode-003"], [], "expected", "", []),
        ("进入后台", ["episode-003"], ["episode-007"], None, "", []),
        ("证据失效", ["episode-006"], [], "failure", "", []),
    ]
    nodes = []
    for index, (title, predecessors, successors, ending_type, question, option_texts) in enumerate(specs, start=1):
        node_id = f"episode-{index:03d}"
        nodes.append({
            "node_id": node_id,
            "node_type": "episode",
            "分集标题": title,
            "route_material": {
                "单集梗概": f"沈砚在控制室推进{title}，当前行动改变证据与关系状态，并形成这一节点不可替代的结果。",
                "本集冲突": f"沈砚必须完成{title}对应的行动并承担现场反馈。",
                "entry_state": {"证据": "公开线索" if node_id == "episode-003" else "待核验", "关系": "合作仍有裂痕"},
                "state_changes": {"证据": "形成当前路线结果", "关系": "因行动发生变化"},
                "allowed_characters": ["沈砚", "顾川"],
                "allowed_scenes": ["控制室"],
                "allowed_props": ["证据盒"],
                "stop_boundary": "停在当前行动的可见结果落地之后，不提前演出后续节点的独占行动与结算。",
            },
            "前置节点编号列表": predecessors,
            "后续节点编号列表": successors,
            "是否结局": ending_type is not None,
            "ending_type": ending_type,
            "互动节点": {
                "是否为分支节点": bool(option_texts),
                "是否有选择问题": bool(option_texts),
                "选择问题": question,
                "选项列表": [
                    {"选项编号": str(number), "选项文字": text, "目标分集编号": target}
                    for number, (text, target) in enumerate(zip(option_texts, successors), start=1)
                ],
                "默认下一分集编号": successors[0] if successors else "无",
            },
            "node_route_material_hash": "",
        })
    route["nodes"] = nodes
    route["edges"], route["choices"], route["endings"] = route_contract.expected_indexes(nodes)
    return route


def recursive_branch_evidence(route: dict) -> dict:
    evidence = planning_evidence(route)
    first = (
        "沈砚在控制室守着唯一的证据盒，警报逼近。她决定守住原案，把证据送往正式核验；"
        "这个决定使她保留了入口，却也让关系裂痕继续存在，所有行动都必须承担不可逆的事实后果。"
    )
    second = (
        "沈砚最终把原案送到核验位置，顾川确认行动留下了不可逆的结果，她承担关系代价并完成自然主线结算。"
        "冻结故事到这里结束，没有预写其他路线的节点形状。"
    )
    evidence["complete_story"]["complete_story"] = first + second
    evidence["mainline_segments"] = [
        {"segment_id": "mainline-001", "source_text": first, "route_node_id": "episode-001"},
        {"segment_id": "mainline-002", "source_text": second, "route_node_id": "episode-002"},
    ]
    evidence["emotional_movements"][0]["reality_shift"] = "三项互斥动作同时成为现实选择"
    evidence["emotional_movements"][1]["source_proof"] = "沈砚最终把原案送到核验位置"
    evidence["decision_fissures"] = [
        {
            "fissure_id": "fissure-001",
            "source_node_id": "episode-001",
            "mainline_position_proof": "沈砚在控制室守着唯一的证据盒",
            "emotional_movement_ids": ["movement-001"],
            "decision_question": "入口行动怎么选？",
            "actions": [
                {
                    "option_text": "守住原案", "target_node_id": "episode-002",
                    "immediate_consequence": "原案立即进入正式核验并保留关系裂痕。",
                    "persistent_differences": {"证据": "正式核验", "关系": "仍有裂痕"},
                    "core_goal_status": "achieved", "consumed_at_node_ids": [],
                },
                {
                    "option_text": "继续追查", "target_node_id": "episode-003",
                    "immediate_consequence": "沈砚公开一条线索并进入新的追查压力。",
                    "persistent_differences": {"证据": "公开线索"},
                    "core_goal_status": "continuing", "consumed_at_node_ids": ["episode-003"],
                },
                {
                    "option_text": "退出调查", "target_node_id": "episode-004",
                    "immediate_consequence": "沈砚永久退出调查并失去再次核验的机会。",
                    "persistent_differences": {"证据": "永久放弃"},
                    "core_goal_status": "abandoned", "consumed_at_node_ids": [],
                },
            ],
            "merge_node_id": None,
            "merge_common_fact": "",
        }
    ]
    evidence["story_treatment"] = {
        "contract_version": "nextplay.episode-story-treatment.v5",
        "title": "证据盒",
        "complete_story": "入口裂缝生长出继续追查路线；该路线未结束，因此再次扫描并形成第二次真实选择。",
        "choices": [
            {
                "choice_id": "choice-001",
                "dramatic_cause": "证据只能支持一项不可撤销的入口行动，沈砚必须立即决定。",
                "question": "入口行动怎么选？",
                "options": [
                    {"option_id": "A", "option_text": "守住原案", "immediate_consequence": "原案立即进入正式核验并保留关系裂痕。", "lasting_difference": "证据进入正式核验且关系仍有裂痕。"},
                    {"option_id": "B", "option_text": "继续追查", "immediate_consequence": "沈砚公开一条线索并进入新的追查压力。", "lasting_difference": "公开线索持续改变后续行动与风险。"},
                    {"option_id": "C", "option_text": "退出调查", "immediate_consequence": "沈砚永久退出调查并失去再次核验的机会。", "lasting_difference": "核心目标被永久放弃并形成小结局。"},
                ],
                "merge_or_ending": "原案结算、继续追查或永久离场，三条路线不被强制拉回同一层。",
            },
            {
                "choice_id": "choice-002",
                "dramatic_cause": "线索公开后风险仍未结算，沈砚必须选择借助公众或进入后台。",
                "question": "公开线索后还要怎么推进？",
                "options": [
                    {"option_id": "A", "option_text": "请求公众见证", "immediate_consequence": "公众见证立即迫使系统公开回应。", "lasting_difference": "公开监督持续保障证据并导向期望结算。"},
                    {"option_id": "B", "option_text": "冒险进入后台", "immediate_consequence": "沈砚绕开监督进入高风险后台核验。", "lasting_difference": "后台风险继续累积并把失败结算推迟到更长支线。"},
                ],
                "merge_or_ending": "公众路线直接结算；后台路线继续一个节点后才进入失败结局。",
            },
        ],
        "endings": [
            {"title": "守住原案", "kind": "main", "causal_payoff": "冻结故事沿原行动自然结算。"},
            {"title": "公开真相", "kind": "expected", "causal_payoff": "公众见证最充分兑现证据目标。"},
            {"title": "证据失效", "kind": "failure", "causal_payoff": "后台冒险推进到主要验证后失败。"},
        ],
        "small_endings": [
            {"title": "主动离场", "kind": "small", "source_action_id": "action-003", "causal_payoff": "退出行动永久中止核心目标。"}
        ],
    }
    evidence["topology_draft_1"] = {
        "entry_node_id": "draft-001",
        "nodes": [
            {"node_id": "draft-001", "kind": "story", "ending_type": None, "successors": ["draft-002"]},
            {"node_id": "draft-002", "kind": "choice", "ending_type": None, "successors": ["draft-003", "draft-004"]},
            {"node_id": "draft-003", "kind": "story", "ending_type": None, "successors": ["draft-005"]},
            {"node_id": "draft-004", "kind": "ending", "ending_type": "small", "successors": []},
            {"node_id": "draft-005", "kind": "ending", "ending_type": "main", "successors": []},
        ],
    }
    evidence["emotional_spine"] = [
        {
            "node_id": node["node_id"], "valence": -0.5 + index * 0.15,
            "arousal": 0.7, "dominance": -0.4 + index * 0.12,
            "turn": node["node_id"] in {"episode-001", "episode-003"},
            "turn_reason": "当前路线出现新的可执行决定裂缝" if node["node_id"] in {"episode-001", "episode-003"} else "",
            "source_quote": "沈砚在控制室",
        }
        for index, node in enumerate(route["nodes"])
    ]
    evidence["route_candidate_hash"] = planning_gate.digest(route)
    return evidence


def write_planning_root(folder: Path, route: dict, evidence: dict) -> None:
    json_values = {
        "user-intent-lock.json": {"constraints": []},
        "creative-brief.json": {"title": evidence["complete_story"]["title"]},
        "complete-story.json": evidence["complete_story"],
        "complete-story-review.json": {"verdict": "PASS"},
        "mainline-decomposition.json": {"mainline_segments": evidence["mainline_segments"]},
        "mainline-emotional-movement.json": {"emotional_movements": evidence["emotional_movements"]},
        "decision-fissure-audit.json": {"decision_fissures": evidence["decision_fissures"]},
        "decision-fissure-review.json": {"verdict": "PASS"},
        "story-treatment.json": evidence["story_treatment"],
        "story-treatment-review.json": {"verdict": "PASS"},
        "topology-draft-1.json": evidence["topology_draft_1"],
        "route-candidate.json": route,
        "topology-review-packet.json": {"status": "sealed"},
        "topology-review-a.json": evidence["reviews"][0],
        "topology-review-b.json": evidence["reviews"][1],
        "emotional-spine.json": {"emotional_spine": evidence["emotional_spine"]},
        "route-material-review.json": {"verdict": "PASS"},
    }
    (folder / "user-request.md").write_text("生成正式流程图", encoding="utf-8")
    for name, value in json_values.items():
        (folder / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def node_draft(route: dict, node_id: str = "episode-001") -> dict:
    node = next(item for item in route["nodes"] if item["node_id"] == node_id)
    script = (
        "【控制室·夜·内】\n"
        "沈砚把证据盒放在操作台中央，屏幕上的红色计时仍在向下跳。顾川伸手去拿，她先按住盒盖。\n"
        "沈砚：你先别碰。盒子一开，我们今晚就只能选一条路。\n"
        "顾川：我知道。可你一直按着它，时间也不会停。\n"
        "沈砚抬头核对门禁回报码，把证据盒推到两人之间。报警声变急，备用线路随即熄灭。\n"
        "沈砚：那就把现状说清楚。原案能保住入口，公开证据能换来外援，提前验证可能烧掉备份，离开就再也回不来。\n"
        "顾川：四条路，只够走一条。你决定，我替你守住门。\n"
        "沈砚收回手，四项行动在屏幕上同时亮起。她没有触碰任何一项，证据盒仍保持封闭。"
    )
    quote = "沈砚把证据盒放在操作台中央"
    checks = [
        {"check": name, "passed": True, "evidence": [quote]}
        for name in sorted(screenplay_contract.REQUIRED_CHECKS)
    ]
    return {
        "contract_version": screenplay_contract.CONTRACT_VERSION,
        "capability_id": screenplay_contract.CAPABILITY_ID,
        "skill_version": screenplay_contract.SKILL_VERSION,
        "project_id": route["project_id"],
        "route_id": route["route_id"],
        "route_version": route["route_version"],
        "route_output_hash": route["route_output_hash"],
        "node_id": node_id,
        "node_route_material_hash": node["node_route_material_hash"],
        "screenplay": {
            "分集剧本": {"完整剧本": script},
            "剧本创作分析": {
                "创作分析": "本集把路线给出的证据压力转成同一控制室内的可执行冲突，让沈砚以按住证据盒的动作掌握决定权。",
                "场景和段落展开计划": "单场先建立倒计时与封闭证据盒，再用顾川的催促形成阻力，最后让四项互斥行动同时成立而不执行。",
                "连续性分析": "入口状态中的证据待核验与关系裂痕均在现场保留；结尾没有执行选项，能够分别进入四个直接后续节点。",
                "冷读与质量问题": "冷读确认命令与回应形成真实话轮，资产均实际入画；未发现越过停止边界或改写路线事实的未修复问题。",
                "验收结论": "PASS",
            },
            "关联角色": ["沈砚", "顾川"],
            "关联场景": ["控制室"],
            "关联道具": ["证据盒"],
            "派生信息": {"实际场次数": 1, "对白人物数": 2},
            "quality_checks": checks,
        },
        "screenplay_hash": "",
        "status": "draft",
        "accepted_at": None,
    }


class EpisodeSkillSplit052Tests(unittest.TestCase):
    def setUp(self):
        self.route = route_contract.seal(candidate_route(), "2026-08-24T00:00:00Z")

    def test_01_route_accepts_plan_and_text_assets_without_screenplays(self):
        self.assertEqual(route_contract.validate(self.route, require_accepted=True), [])
        corpus = json.dumps(self.route, ensure_ascii=False)
        self.assertNotIn("完整剧本", corpus)
        self.assertNotIn("剧本创作分析", corpus)

    def test_02_route_can_be_saved_and_displayed_with_no_script_fields(self):
        self.assertEqual(self.route["route_status"], "accepted")
        self.assertTrue(self.route["route_output_hash"])
        self.assertTrue(all(node["分集标题"] and node["route_material"]["单集梗概"] for node in self.route["nodes"]))

    def test_03_route_acceptance_does_not_enter_screenplay_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            output = folder / "route.json"
            route = candidate_route()
            write_planning_root(folder, route, planning_evidence(route))
            planning = subprocess.run(
                [sys.executable, str(ROUTE_SKILL / "scripts" / "planning_gate.py"), "create", str(folder)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(planning.returncode, 0, planning.stdout + planning.stderr)
            self.assertIn("PLANNING_ACCEPTED", planning.stdout.splitlines())
            result = subprocess.run(
                [sys.executable, str(ROUTE_SKILL / "scripts" / "accept_route.py"), str(folder), str(output), "--accepted-at", "2026-08-24T00:00:00Z"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ROUTE_ACCEPTED", result.stdout.splitlines())
            self.assertFalse(any("screenplay" in path.name or "剧本" in path.name for path in folder.iterdir()))

    def test_03b_route_rejects_missing_or_stale_planning_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            route = candidate_route()
            output = folder / "route.json"
            write_planning_root(folder, route, planning_evidence(route))
            planning_gate.atomic_json(folder / "planning-acceptance.json", planning_gate.build_from_root(folder))
            route["route_version"] = "2"
            (folder / "route-candidate.json").write_text(json.dumps(route, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROUTE_SKILL / "scripts" / "accept_route.py"), str(folder), str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("规划验收未通过", result.stdout)
            self.assertFalse(output.exists())

    def test_03g_workflow_exposes_only_one_052_next_action(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            state = workflow_state.status(folder)
            self.assertEqual(state["next_actions"][0]["action"], "CAPTURE_USER_REQUEST")
            (folder / "user-request.md").write_text("生成路线", encoding="utf-8")
            state = workflow_state.status(folder)
            self.assertEqual(len(state["next_actions"]), 1)
            self.assertEqual(state["next_actions"][0]["action"], "BUILD_USER_INTENT_LOCK")

    def test_03h_workflow_rejects_final_topology_before_upstream_files(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "route-candidate.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "提前创建"):
                workflow_state.status(folder)

    def test_03i_planning_receipt_freezes_every_stage_file(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            route = candidate_route()
            write_planning_root(folder, route, planning_evidence(route))
            planning_gate.atomic_json(folder / "planning-acceptance.json", planning_gate.build_from_root(folder))
            self.assertEqual(planning_gate.verify_root(folder), [])
            (folder / "complete-story-review.json").write_text('{"verdict":"FAIL"}', encoding="utf-8")
            self.assertTrue(any("失效" in issue or "变化" in issue for issue in planning_gate.verify_root(folder)))

    def test_03c_planning_gate_rejects_same_topology_shape(self):
        route = candidate_route()
        evidence = planning_evidence(route)
        evidence["topology_draft_1"] = {
            "entry_node_id": "episode-001",
            "nodes": [
                {
                    "node_id": node["node_id"],
                    "kind": "ending" if node["是否结局"] else ("choice" if node["互动节点"]["是否为分支节点"] else "story"),
                    "ending_type": node["ending_type"],
                    "successors": node["后续节点编号列表"],
                }
                for node in route["nodes"]
            ],
        }
        issues = planning_gate.validate(route, evidence)
        self.assertTrue(any("图形指纹相同" in issue for issue in issues), issues)

    def test_03d_planning_gate_rejects_unreviewed_branch(self):
        route = candidate_route()
        evidence = planning_evidence(route)
        evidence["decision_fissures"] = []
        issues = planning_gate.validate(route, evidence)
        self.assertTrue(any("未全部经过主线裂缝审计" in issue for issue in issues), issues)

    def test_03j_branch_node_can_open_another_branch_and_outgrow_mainline(self):
        route = recursive_branch_route()
        evidence = recursive_branch_evidence(route)
        self.assertEqual(route_contract.validate(route, require_accepted=False), [])
        self.assertEqual(planning_gate.validate(route, evidence), [])
        mainline_path = ["episode-001", "episode-002"]
        longer_branch_path = ["episode-001", "episode-003", "episode-006", "episode-007"]
        self.assertGreater(len(longer_branch_path), len(mainline_path))
        self.assertNotIn("episode-003", {item["route_node_id"] for item in evidence["mainline_segments"]})
        self.assertTrue(route["nodes"][2]["互动节点"]["是否为分支节点"])

    def test_03k_unregistered_recursive_branch_is_rejected(self):
        route = recursive_branch_route()
        evidence = recursive_branch_evidence(route)
        evidence["story_treatment"]["choices"] = evidence["story_treatment"]["choices"][:1]
        issues = planning_gate.validate(route, evidence)
        self.assertTrue(any("支线事实选择与正式拓扑选择不一致" in issue for issue in issues), issues)

    def test_03e_planning_gate_rejects_fake_review_quote(self):
        route = candidate_route()
        evidence = planning_evidence(route)
        evidence["reviews"][0]["checks"][0]["evidence_quote"] = "这句话根本不在当前封闭材料包中"
        issues = planning_gate.validate(route, evidence)
        self.assertTrue(any("缺少当前材料逐字证据" in issue for issue in issues), issues)

    def test_03f_planning_gate_rejects_unconsumed_persistent_difference(self):
        route = candidate_route()
        episode_three = route["nodes"][2]
        episode_three["是否结局"] = False
        episode_three["ending_type"] = None
        episode_three["后续节点编号列表"] = ["episode-002"]
        episode_three["互动节点"]["默认下一分集编号"] = "episode-002"
        evidence = planning_evidence(route)
        action = evidence["decision_fissures"][0]["actions"][1]
        action["core_goal_status"] = "continuing"
        action["persistent_differences"] = {"公开证据": "已经公开"}
        action["consumed_at_node_ids"] = ["episode-002"]
        evidence["route_candidate_hash"] = planning_gate.digest(route)
        issues = planning_gate.validate(route, evidence)
        self.assertTrue(any("持续差异未被登记节点实际消费" in issue for issue in issues), issues)

    def test_04_screenplay_skill_accepts_exactly_one_node(self):
        patch = screenplay_contract.seal(self.route, node_draft(self.route), "2026-08-24T00:01:00Z")
        self.assertEqual(patch["node_id"], "episode-001")
        self.assertNotIn("nodes", patch)
        self.assertEqual(patch["status"], "accepted")

    def test_05_node_generation_does_not_change_graph(self):
        before = {key: copy.deepcopy(self.route[key]) for key in ("nodes", "edges", "choices", "endings")}
        screenplay_contract.seal(self.route, node_draft(self.route), "2026-08-24T00:01:00Z")
        after = {key: self.route[key] for key in before}
        self.assertEqual(before, after)

    def test_06_route_version_change_invalidates_old_node_input(self):
        old_draft = node_draft(self.route)
        new_candidate = candidate_route()
        new_candidate["route_version"] = "2"
        new_route = route_contract.seal(new_candidate, "2026-08-24T00:02:00Z")
        issues = screenplay_contract.validate(new_route, old_draft, require_accepted=False)
        self.assertTrue(any("ROUTE_DEPENDENCY_ERROR" in issue for issue in issues))

    def test_07_one_node_failure_preserves_route_and_other_node(self):
        route_before = json.dumps(self.route, ensure_ascii=False, sort_keys=True)
        good = screenplay_contract.seal(self.route, node_draft(self.route), "2026-08-24T00:01:00Z")
        bad = node_draft(self.route)
        bad["node_id"] = "episode-999"
        with self.assertRaises(ValueError):
            screenplay_contract.seal(self.route, bad)
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            route_path = folder / "route.json"
            draft_path = folder / "bad.json"
            output_path = folder / "must-not-exist.json"
            route_path.write_text(json.dumps(self.route, ensure_ascii=False), encoding="utf-8")
            draft_path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_SKILL / "scripts" / "accept_node_screenplay.py"), str(route_path), str(draft_path), str(output_path)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output_path.exists())
        self.assertEqual(route_before, json.dumps(self.route, ensure_ascii=False, sort_keys=True))
        self.assertEqual(good["status"], "accepted")

    def test_08_field_ownership_has_no_overlap_or_gap(self):
        table = json.loads((SPLIT / "field-ownership.json").read_text(encoding="utf-8"))
        ownership = table["ownership"]
        self.assertTrue(ownership)
        for value in ownership.values():
            self.assertNotEqual(value["route_write"], value["screenplay_write"])
        covered = set()
        for name in ownership:
            covered.add(name.split(".", 1)[0])
        self.assertEqual(covered - {"剧本创作分析"}, set(table["original_required_fields"]))

    def test_09_production_packages_exclude_nonproduction_artifacts(self):
        forbidden_parts = {"tests", "fixtures", "fixture", "cache", "__pycache__", "tmp", "temp"}
        for skill in (ROUTE_SKILL, SCRIPT_SKILL):
            for path in skill.rglob("*"):
                relative = path.relative_to(skill)
                self.assertFalse(forbidden_parts & set(relative.parts), relative)
                self.assertFalse(path.name.endswith((".log", ".pyc", ".tmp")), relative)

    def test_10_manifests_and_slugs_match_split_contract(self):
        route_manifest = json.loads((ROUTE_SKILL / "reference-manifest.json").read_text(encoding="utf-8"))
        script_manifest = json.loads((SCRIPT_SKILL / "reference-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(route_manifest["baseline"], "episode-generator-biz")
        self.assertEqual(script_manifest["baseline"], "episode-generator-biz")
        self.assertIn("name: episode-route-planner-biz", (ROUTE_SKILL / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("name: episode-screenwriter-biz", (SCRIPT_SKILL / "SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue((ROUTE_SKILL / "references" / "business-interface.md").is_file())
        self.assertTrue((SCRIPT_SKILL / "references" / "business-interface.md").is_file())
        production_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for skill in (ROUTE_SKILL, SCRIPT_SKILL)
            for path in skill.rglob("*")
            if path.is_file()
        )
        self.assertNotIn("0.52", production_text)


if __name__ == "__main__":
    unittest.main()
