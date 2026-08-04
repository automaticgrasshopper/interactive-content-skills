#!/usr/bin/env python3
"""Project validated episode business JSON into a Nextplay route proposal.

The route contains video episode nodes and independent choice nodes. Business
choices remain declared once on their source episode and project to one choice
node with deterministic default/choice edges.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from assemble_business_output import BUSINESS_SKILL_VERSION, build_business_output
from completion_gate import validate_receipt
from validate_and_assemble_scripts import atomic_write
from validate_business_output import validate as validate_business_output
from validate_route_projection import validate as validate_route_projection


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label}必须是boolean，禁止使用‘是/否’字符串")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}顶层必须是object")
    return value


def asset_map(assets: dict[str, Any]) -> dict[str, str]:
    rows = assets.get("data", {}).get("assets", [])
    if not isinstance(rows, list):
        raise ValueError("assets.json/data/assets必须是list")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("assets.json含非法资产记录")
        name = row.get("name")
        ref_id = row.get("ref_id")
        if isinstance(name, str) and name.strip() and isinstance(ref_id, str) and ref_id.strip():
            result[name] = ref_id
    return result


def mentions(episode: dict[str, Any], refs: dict[str, str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for field, role in (("关联角色", "character"), ("关联场景", "scene"), ("关联道具", "item")):
        for name in episode[field]:
            if name not in refs:
                raise ValueError(f"业务分集引用未落库资产：{field}/{name}")
            result.append(
                {
                    "type": "asset",
                    "category": role,
                    "ref_id": refs[name],
                    "display": name,
                }
            )
    return result


def build_route(
    business: dict[str, Any],
    base_route: dict[str, Any],
    assets: dict[str, Any],
    outline_revision: int,
    assets_revision: int,
) -> dict[str, Any]:
    episodes = business.get("分集列表")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("分集列表必须是非空list")
    refs = asset_map(assets)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # The web route uses one continuous episode_ref sequence for every visible
    # card, including choice cards. Business episode ids remain untouched and
    # are carried in metadata. This prevents the web view from renumbering
    # choice targets or treating the first choice as the route origin.
    episode_route_refs: dict[str, str] = {}
    choice_route_refs: dict[str, str] = {}
    choice_ids_by_episode = {
        episode["分集编号"]: f"choice-{index:03d}"
        for index, episode in enumerate(
            (episode for episode in episodes if episode["互动节点"]["是否有选择问题"] is True),
            1,
        )
    }
    visible_order: list[tuple[str, dict[str, Any]]] = []
    visible_index = 1
    for episode in episodes:
        episode_id = episode["分集编号"]
        route_ref = f"episode-{visible_index:03d}"
        episode_route_refs[episode_id] = route_ref
        visible_order.append(("episode", episode))
        visible_index += 1
        interaction = episode["互动节点"]
        if interaction["是否有选择问题"] is True:
            choice_id = choice_ids_by_episode[episode_id]
            choice_route_refs[choice_id] = f"episode-{visible_index:03d}"
            visible_order.append(("choice", episode))
            visible_index += 1

    for logical_type, episode in visible_order:
        if not isinstance(episode, dict):
            raise ValueError("分集列表含非法记录")
        episode_id = episode["分集编号"]
        interaction = episode["互动节点"]
        has_choice = require_bool(interaction["是否有选择问题"], f"{episode_id}/是否有选择问题")
        is_branch = require_bool(interaction["是否为分支节点"], f"{episode_id}/是否为分支节点")
        if is_branch != has_choice:
            raise ValueError(f"{episode_id}分支与选择声明不一致")
        is_ending = require_bool(episode["是否结局"], f"{episode_id}/是否结局")
        options = interaction["选项列表"]

        if logical_type == "choice":
            choice_id = choice_ids_by_episode[episode_id]
            route_node_ref = choice_route_refs[choice_id]
            option_edge_refs: list[str] = []
            for index, option in enumerate(options, 1):
                edge_ref = f"edge-{route_node_ref[-3:]}-{index:02d}"
                option_edge_refs.append(edge_ref)
                target_ref = episode_route_refs[option["目标分集编号"]]
                edges.append(
                    {
                        "edge_ref": edge_ref,
                        "source_node_ref": route_node_ref,
                        "target_node_ref": target_ref,
                        "edge_type": "choice",
                        "choice": {
                            "label": str(option["选项文字"]),
                            "description": "",
                            "intent": str(option["选项文字"]),
                        },
                        "conditions": {"visible": [], "enabled": []},
                        "effects": {"on_choose": []},
                        "priority": index,
                        "metadata": {
                            "choice_ref": choice_id,
                            "target_business_episode_ref": option["目标分集编号"],
                        },
                    }
                )
            choice_script = episode["分集剧本"]["单集梗概"].strip()
            if not choice_script:
                raise ValueError(f"{choice_id}缺少可供网页先播放的选择前剧情")
            nodes.append(
                {
                    "node_ref": route_node_ref,
                    "node_type": "choice",
                    "episode_ref": route_node_ref,
                    "title": interaction["选择问题"],
                    "summary": choice_script,
                    "content": {
                        "script": {"text": choice_script, "mentions": mentions(episode, refs)},
                        "conflict": episode["剧本分析"]["本集冲突"],
                        "objective": "",
                        "mood": "",
                    },
                    "interaction": {
                        "interaction_ref": choice_id,
                        "has_interaction": True,
                        "question": interaction["选择问题"],
                        "after_plot_beat": choice_script,
                        "option_edge_refs": option_edge_refs,
                    },
                    "assets": {
                        "character_refs": [refs[name] for name in episode["关联角色"]],
                        "scene_refs": [refs[name] for name in episode["关联场景"]],
                        "item_refs": [refs[name] for name in episode["关联道具"]],
                    },
                    "timeline": {"clips": []},
                    "playback": {
                        "mode": "interactive",
                        "auto_advance": False,
                        "default_next_edge_ref": None,
                    },
                    "conditions": {"enter": []},
                    "effects": {"on_enter": [], "on_exit": []},
                    "metadata": {
                        "is_ending": False,
                        "logical_node_type": "choice",
                        "choice_ref": choice_id,
                        "source_business_episode_ref": episode_id,
                    },
                }
            )
            continue

        route_node_ref = episode_route_refs[episode_id]
        if has_choice:
            choice_id = choice_ids_by_episode[episode_id]
            bridge_edge_ref = f"edge-{route_node_ref[-3:]}-choice"
            edges.append(
                {
                    "edge_ref": bridge_edge_ref,
                    "source_node_ref": route_node_ref,
                    "target_node_ref": choice_route_refs[choice_id],
                    "edge_type": "default",
                    "choice": None,
                    "conditions": {"visible": [], "enabled": []},
                    "effects": {"on_choose": []},
                    "priority": 1,
                    "metadata": {},
                }
            )
        else:
            for index, target in enumerate(episode["剧本分析"]["后续节点编号列表"], 1):
                edge_ref = f"edge-{route_node_ref[-3:]}-{index:02d}"
                edges.append(
                    {
                        "edge_ref": edge_ref,
                        "source_node_ref": route_node_ref,
                        "target_node_ref": episode_route_refs[target],
                        "edge_type": "default",
                        "choice": None,
                        "conditions": {"visible": [], "enabled": []},
                        "effects": {"on_choose": []},
                        "priority": index,
                        "metadata": {},
                    }
                )

        successors = episode["剧本分析"]["后续节点编号列表"]
        nodes.append(
            {
                "node_ref": route_node_ref,
                "node_type": "video",
                "episode_ref": route_node_ref,
                "title": episode["分集标题"],
                "summary": episode["分集剧本"]["单集梗概"],
                "content": {
                    "script": {
                        "text": episode["分集剧本"]["完整剧本"],
                        "mentions": mentions(episode, refs),
                    },
                    "conflict": episode["剧本分析"]["本集冲突"],
                    "objective": "",
                    "mood": "",
                },
                "interaction": {
                    "interaction_ref": None,
                    "has_interaction": False,
                    "question": None,
                    "after_plot_beat": None,
                    "option_edge_refs": [],
                },
                "assets": {
                    "character_refs": [refs[name] for name in episode["关联角色"]],
                    "scene_refs": [refs[name] for name in episode["关联场景"]],
                    "item_refs": [refs[name] for name in episode["关联道具"]],
                },
                "timeline": {"clips": []},
                "playback": {
                    "mode": "linear",
                    "auto_advance": True,
                    "default_next_edge_ref": (
                        f"edge-{route_node_ref[-3:]}-choice"
                        if has_choice
                        else (None if not successors else f"edge-{route_node_ref[-3:]}-01")
                    ),
                },
                "conditions": {"enter": []},
                "effects": {"on_enter": [], "on_exit": []},
                "metadata": {
                    "is_ending": is_ending,
                    "logical_node_type": "episode",
                    "business_episode_ref": episode_id,
                },
            }
        )

    route = copy.deepcopy(base_route)
    route["depends_on"] = {
        "outline_revision": outline_revision,
        "assets_revision": assets_revision,
    }
    route["data"] = {
        "route_ref": base_route.get("data", {}).get("route_ref", "main_route"),
        "entry_node_ref": episode_route_refs[episodes[0]["分集编号"]],
        "nodes": nodes,
        "edges": edges,
    }
    route.pop("settings", None)
    return route


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("business_json", type=Path)
    parser.add_argument("base_route", type=Path)
    parser.add_argument("assets_json", type=Path)
    parser.add_argument("output_route", type=Path)
    parser.add_argument("--outline-revision", type=int, required=True)
    parser.add_argument("--assets-revision", type=int, required=True)
    parser.add_argument("--asset-catalog", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--completion-receipt", type=Path, required=True)
    parser.add_argument("--character-introductions", type=Path)
    parser.add_argument("--spine", type=Path)
    parser.add_argument("--expected-endings", type=int, required=True)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--allowed-changed", action="append", default=[])
    parser.add_argument("--change-scope", choices=("any", "dialogue"), default="any")
    args = parser.parse_args()
    try:
        cache_root = args.cache_root.resolve()
        public_dir = args.public_dir.resolve()
        asset_catalog_path = args.asset_catalog.resolve()
        character_introductions_path = (
            args.character_introductions
            or cache_root / "character-introductions.json"
        ).resolve()
        spine_path = (args.spine or cache_root / "emotional-spine.json").resolve()
        baseline = load_json(args.baseline) if args.baseline else None
        business = load_json(args.business_json)
        issues = validate_business_output(
            business,
            args.asset_catalog,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
            baseline,
            set(args.allowed_changed),
            args.change_scope,
        )
        if issues:
            raise ValueError("业务输出未通过：" + "；".join(issues))
        rebuilt, completion_issues = build_business_output(
            cache_root,
            public_dir,
            asset_catalog_path,
            character_introductions_path,
            spine_path,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
            baseline,
            args.baseline_root.resolve() if args.baseline_root else None,
            set(args.allowed_changed),
            args.change_scope,
        )
        if completion_issues:
            raise ValueError("完整生成流程未通过：" + "；".join(completion_issues))
        if rebuilt != business:
            raise ValueError("业务JSON不是由当前已通过的冻结结果生成")
        receipt_issues = validate_receipt(
            args.completion_receipt.resolve(),
            cache_root,
            public_dir,
            args.business_json.resolve(),
            asset_catalog_path,
            character_introductions_path,
            spine_path,
            BUSINESS_SKILL_VERSION,
        )
        if receipt_issues:
            raise ValueError("；".join(receipt_issues))
        route = build_route(
            business,
            load_json(args.base_route),
            load_json(args.assets_json),
            args.outline_revision,
            args.assets_revision,
        )
        route_issues = validate_route_projection(business, route)
        if route_issues:
            raise ValueError("路线投影未通过：" + "；".join(route_issues))
        atomic_write(
            args.output_route,
            json.dumps(route, ensure_ascii=False, indent=2) + "\n",
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    episode_count = sum(node.get("node_type") == "video" for node in route["data"]["nodes"])
    choice_count = sum(node.get("node_type") == "choice" for node in route["data"]["nodes"])
    print(
        f"PASS: projected {episode_count} video episode nodes + "
        f"{choice_count} independent choice nodes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
