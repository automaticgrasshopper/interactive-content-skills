#!/usr/bin/env python3
"""Project validated episode business JSON into a Nextplay route proposal.

The route contains only playable episode nodes. Choices remain interactions on
their source episode and are represented exactly once by choice edges.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

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

    for episode in episodes:
        if not isinstance(episode, dict):
            raise ValueError("分集列表含非法记录")
        episode_id = episode["分集编号"]
        choice = episode["选择节点"]
        interaction = episode["互动节点"]
        if require_bool(interaction["是否为互动节点"], f"{episode_id}/是否为互动节点") is not True:
            raise ValueError(f"{episode_id}不是互动节点")
        if require_bool(choice["是否为选择节点"], f"{episode_id}/是否为选择节点") is not False:
            raise ValueError(f"{episode_id}不得作为独立选择节点")
        has_choice = require_bool(choice["是否有选择问题"], f"{episode_id}/是否有选择问题")
        if require_bool(interaction["后边是否接选择节点"], f"{episode_id}/后边是否接选择节点") != has_choice:
            raise ValueError(f"{episode_id}互动与选择声明不一致")
        is_ending = require_bool(episode["是否结局"], f"{episode_id}/是否结局")
        options = choice["选项列表"]
        option_edge_refs: list[str] = []

        if has_choice:
            choice_id = choice["选择节点编号"]
            bridge_edge_ref = f"edge-{episode_id[-3:]}-choice"
            edges.append(
                {
                    "edge_ref": bridge_edge_ref,
                    "source_node_ref": episode_id,
                    "target_node_ref": choice_id,
                    "edge_type": "default",
                    "choice": None,
                    "conditions": {"visible": [], "enabled": []},
                    "effects": {"on_choose": []},
                    "priority": 1,
                    "metadata": {},
                }
            )
            for index, option in enumerate(options, 1):
                edge_ref = f"edge-{episode_id[-3:]}-{index:02d}"
                option_edge_refs.append(edge_ref)
                edges.append(
                    {
                        "edge_ref": edge_ref,
                        "source_node_ref": choice_id,
                        "target_node_ref": option["目标互动节点编号"],
                        "edge_type": "choice",
                        "choice": {
                            "label": str(option["选项文字"]),
                            "description": "",
                            "intent": str(option["选项文字"]),
                        },
                        "conditions": {"visible": [], "enabled": []},
                        "effects": {"on_choose": []},
                        "priority": index,
                        "metadata": {"choice_ref": choice["选择节点编号"]},
                    }
                )
        else:
            for index, target in enumerate(episode["剧本分析"]["后续节点编号列表"], 1):
                edge_ref = f"edge-{episode_id[-3:]}-{index:02d}"
                edges.append(
                    {
                        "edge_ref": edge_ref,
                        "source_node_ref": episode_id,
                        "target_node_ref": target,
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
                "node_ref": episode_id,
                "node_type": "video",
                "episode_ref": episode_id,
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
                        f"edge-{episode_id[-3:]}-choice"
                        if has_choice
                        else (None if not successors else f"edge-{episode_id[-3:]}-01")
                    ),
                },
                "conditions": {"enter": []},
                "effects": {"on_enter": [], "on_exit": []},
                "metadata": {"is_ending": is_ending},
            }
        )

        if has_choice:
            choice_id = choice["选择节点编号"]
            nodes.append(
                {
                    "node_ref": choice_id,
                    "node_type": "choice",
                    "episode_ref": episode_id,
                    "title": choice["选择问题"],
                    "summary": "",
                    "content": {
                        "script": {"text": "", "mentions": []},
                        "conflict": "",
                        "objective": "",
                        "mood": "",
                    },
                    "interaction": {
                        "interaction_ref": choice_id,
                        "has_interaction": True,
                        "question": choice["选择问题"],
                        "after_plot_beat": episode["分集剧本"]["单集梗概"],
                        "option_edge_refs": option_edge_refs,
                    },
                    "assets": {
                        "character_refs": [],
                        "scene_refs": [],
                        "item_refs": [],
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
                        "source_episode_ref": episode_id,
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
        "entry_node_ref": episodes[0]["分集编号"],
        "nodes": nodes,
        "edges": edges,
    }
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
    parser.add_argument("--expected-endings", type=int, required=True)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    args = parser.parse_args()
    try:
        business = load_json(args.business_json)
        issues = validate_business_output(
            business,
            args.asset_catalog,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
            None,
            set(),
            "any",
        )
        if issues:
            raise ValueError("业务输出未通过：" + "；".join(issues))
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
        args.output_route.parent.mkdir(parents=True, exist_ok=True)
        args.output_route.write_text(json.dumps(route, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
