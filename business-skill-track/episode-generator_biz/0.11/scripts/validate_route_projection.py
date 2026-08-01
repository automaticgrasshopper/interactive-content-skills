#!/usr/bin/env python3
"""Cross-check a Nextplay route projection against validated business JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}顶层必须是object")
    return value


def validate(business: dict[str, Any], route: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    episodes = business.get("分集列表")
    data = route.get("data")
    if not isinstance(episodes, list) or not episodes:
        return ["分集列表必须是非空list"]
    if not isinstance(data, dict):
        return ["route/data必须是object"]
    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["route nodes/edges必须是list"]

    episode_ids = [episode.get("分集编号") for episode in episodes]
    node_ids = [node.get("node_ref") for node in nodes if isinstance(node, dict)]
    if len(nodes) != len(episodes):
        issues.append(f"路线剧情节点数错误：期望{len(episodes)}，实际{len(nodes)}")
    if node_ids != episode_ids:
        issues.append("路线节点顺序或编号与分集列表不一致")
    if data.get("entry_node_ref") != "episode-001" or not episode_ids or episode_ids[0] != "episode-001":
        issues.append("唯一入口必须是episode-001")
    if any(isinstance(node_id, str) and node_id.startswith("choice-") for node_id in node_ids):
        issues.append("route nodes不得包含独立choice节点")

    node_by_id = {node.get("node_ref"): node for node in nodes if isinstance(node, dict)}
    edge_by_id: dict[str, dict[str, Any]] = {}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        if not isinstance(edge, dict):
            issues.append("route含非法edge")
            continue
        edge_ref = edge.get("edge_ref")
        if not isinstance(edge_ref, str) or not edge_ref or edge_ref in edge_by_id:
            issues.append(f"edge_ref非法或重复：{edge_ref}")
            continue
        edge_by_id[edge_ref] = edge
        source = edge.get("source_node_ref")
        target = edge.get("target_node_ref")
        if source not in node_by_id or target not in node_by_id:
            issues.append(f"悬空连线：{source}->{target}")
        outgoing[source].append(edge)
        incoming[target].append(edge)

    seen_interactions: set[str] = set()
    expected_choice_count = 0
    ending_ids: set[str] = set()
    for episode in episodes:
        episode_id = episode["分集编号"]
        node = node_by_id.get(episode_id)
        if not isinstance(node, dict):
            continue
        choice = episode["选择节点"]
        interaction_record = episode["互动节点"]
        has_choice = choice["是否有选择问题"]
        if not isinstance(has_choice, bool):
            issues.append(f"{episode_id}/是否有选择问题不是boolean")
            continue
        if choice["是否为选择节点"] is not False or interaction_record["是否为互动节点"] is not True:
            issues.append(f"{episode_id}/业务节点身份错误")
        if node.get("node_type") != "video" or node.get("episode_ref") != episode_id:
            issues.append(f"{episode_id}/路线节点不是对应视频剧情节点")
        script_text = node.get("content", {}).get("script", {}).get("text")
        expected_script = episode["分集剧本"]["完整剧本"]
        if not isinstance(script_text, str) or not script_text.strip() or script_text != expected_script:
            issues.append(f"{episode_id}/完整剧情缺失或被替换")
        if episode_id == "episode-001" and has_choice and len(re.sub(r"\s+", "", script_text or "")) < 60:
            issues.append("episode-001带选择时必须先渲染不少于60个非空白字符的剧情")
        if node.get("metadata", {}).get("is_ending") is not episode["是否结局"]:
            issues.append(f"{episode_id}/结局标记投影错误")
        if episode["是否结局"]:
            ending_ids.add(episode_id)

        interaction = node.get("interaction")
        if not isinstance(interaction, dict):
            issues.append(f"{episode_id}/缺少interaction对象")
            continue
        if interaction.get("has_interaction") is not has_choice:
            issues.append(f"{episode_id}/has_interaction必须与boolean选择标记一致")
        actual_edges = outgoing.get(episode_id, [])
        expected_targets = episode["剧本分析"]["后续节点编号列表"]
        if [edge.get("target_node_ref") for edge in actual_edges] != expected_targets:
            issues.append(f"{episode_id}/后续连线顺序或目标错误")

        if has_choice:
            expected_choice_count += 1
            choice_id = choice["选择节点编号"]
            if choice_id in seen_interactions:
                issues.append(f"选择节点重复：{choice_id}")
            seen_interactions.add(choice_id)
            if interaction.get("interaction_ref") != choice_id:
                issues.append(f"{episode_id}/interaction_ref错误")
            if interaction.get("question") != choice["选择问题"]:
                issues.append(f"{episode_id}/选择问题投影错误")
            option_refs = interaction.get("option_edge_refs")
            if option_refs != [edge.get("edge_ref") for edge in actual_edges]:
                issues.append(f"{episode_id}/选择边引用错误")
            options = choice["选项列表"]
            if len(actual_edges) != len(options):
                issues.append(f"{episode_id}/选择边数量错误")
            for edge, option in zip(actual_edges, options):
                if edge.get("edge_type") != "choice":
                    issues.append(f"{episode_id}/选择被投影为非choice边")
                if edge.get("choice", {}).get("label") != option["选项文字"]:
                    issues.append(f"{episode_id}/选项文字投影错误")
                if edge.get("metadata", {}).get("choice_ref") != choice_id:
                    issues.append(f"{episode_id}/choice_ref错误")
        else:
            if interaction.get("interaction_ref") is not None or interaction.get("question") is not None or interaction.get("option_edge_refs") not in ([], None):
                issues.append(f"{episode_id}/无选择节点含选择投影")
            if any(edge.get("edge_type") != "default" for edge in actual_edges):
                issues.append(f"{episode_id}/普通后继必须使用default边")

        if episode["是否结局"] and actual_edges:
            issues.append(f"{episode_id}/结局节点不得有后续连线")
        if not episode["是否结局"] and not actual_edges:
            issues.append(f"{episode_id}/非结局节点不得成为死路")

    expected_visible_total = len(episodes) + expected_choice_count
    if len(seen_interactions) != expected_choice_count:
        issues.append("唯一选择节点数量错误")
    if incoming.get("episode-001"):
        issues.append("episode-001不得有前置连线")

    reachable: set[str] = set()
    queue = deque(["episode-001"])
    while queue:
        current = queue.popleft()
        if current in reachable or current not in node_by_id:
            continue
        reachable.add(current)
        queue.extend(edge.get("target_node_ref") for edge in outgoing.get(current, []))
    if reachable != set(episode_ids):
        issues.append(f"存在不可达剧情节点：{sorted(set(episode_ids) - reachable)}")

    can_end = set(ending_ids)
    changed = True
    while changed:
        changed = False
        for edge in edges:
            source = edge.get("source_node_ref")
            target = edge.get("target_node_ref")
            if target in can_end and source not in can_end:
                can_end.add(source)
                changed = True
    if can_end != set(episode_ids):
        issues.append(f"存在无法抵达结局的剧情节点：{sorted(set(episode_ids) - can_end)}")

    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("business_json", type=Path)
    parser.add_argument("route_json", type=Path)
    args = parser.parse_args()
    try:
        business = load(args.business_json)
        route = load(args.route_json)
        issues = validate(business, route)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    episode_count = len(business["分集列表"])
    choice_count = sum(episode["选择节点"]["是否有选择问题"] for episode in business["分集列表"])
    print(
        f"PASS: {episode_count} episode nodes + {choice_count} unique choice nodes; "
        f"expected visible total {episode_count + choice_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
