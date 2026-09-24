#!/usr/bin/env python3
"""Validate and seal the route-only handoff."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "nextplay.episode-route-handoff.v1"
CAPABILITY_ID = "episode-route-planner-biz"
ROOT_FIELDS = {
    "contract_version", "capability_id", "project_id", "route_id",
    "route_version", "route_status", "route_input_hash", "route_output_hash", "accepted_at",
    "nodes", "edges", "choices", "endings",
}
NODE_FIELDS = {
    "node_id", "node_type", "分集标题", "route_material", "前置节点编号列表",
    "后续节点编号列表", "是否结局", "ending_type", "互动节点",
    "node_route_material_hash",
}
MATERIAL_FIELDS = {
    "单集梗概", "本集冲突", "entry_state", "state_changes", "allowed_characters",
    "allowed_scenes", "allowed_props", "stop_boundary",
}
INTERACTION_FIELDS = {
    "是否为分支节点", "是否有选择问题", "选择问题", "选项列表", "默认下一分集编号",
}
OPTION_FIELDS = {"选项编号", "选项文字", "目标分集编号"}
EDGE_FIELDS = {"edge_id", "source_node_id", "target_node_id", "edge_type"}
CHOICE_FIELDS = {"source_node_id", "选项编号", "选项文字", "目标分集编号"}
ENDING_FIELDS = {"node_id", "ending_type"}
ENDING_TYPES = {"main", "expected", "failure", "small"}
EPISODE_ID = re.compile(r"episode-\d{3,}")
HASH = re.compile(r"[0-9a-f]{64}")



def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def node_hash(node: dict[str, Any]) -> str:
    value = deepcopy(node)
    value.pop("node_route_material_hash", None)
    return digest(value)


def route_hash(route: dict[str, Any]) -> str:
    value = deepcopy(route)
    value.pop("route_output_hash", None)
    value.pop("accepted_at", None)
    return digest(value)


def non_placeholder(value: Any, minimum: int) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def string_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) == len(set(value)) and all(isinstance(item, str) and item.strip() for item in value)


def exact_keys(value: Any, expected: set[str], label: str, issues: list[str]) -> bool:
    if not isinstance(value, dict) or set(value) != expected:
        issues.append(f"{label}字段错误")
        return False
    return True


def expected_indexes(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, str]]]:
    edges: list[dict[str, str]] = []
    choices: list[dict[str, Any]] = []
    endings: list[dict[str, str]] = []
    edge_number = 1
    for node in nodes:
        source = node["node_id"]
        interaction = node["互动节点"]
        options = interaction["选项列表"]
        option_targets = {item["目标分集编号"] for item in options}
        for target in node["后续节点编号列表"]:
            edges.append({
                "edge_id": f"edge-{edge_number:03d}",
                "source_node_id": source,
                "target_node_id": target,
                "edge_type": "choice" if target in option_targets else "default",
            })
            edge_number += 1
        for option in options:
            choices.append({"source_node_id": source, **option})
        if node["是否结局"]:
            endings.append({"node_id": source, "ending_type": node["ending_type"]})
    return edges, choices, endings


def validate(route: Any, *, require_accepted: bool) -> list[str]:
    issues: list[str] = []
    if not exact_keys(route, ROOT_FIELDS, "路线根对象", issues):
        return issues
    if route["contract_version"] != CONTRACT_VERSION or route["capability_id"] != CAPABILITY_ID:
        issues.append("路线合同或能力标识错误")
    for field in ("project_id", "route_id", "route_version"):
        if not isinstance(route[field], str) or not route[field].strip():
            issues.append(f"{field}为空")
    if HASH.fullmatch(str(route["route_input_hash"] or "")) is None:
        issues.append("route_input_hash必须是SHA-256")
    expected_status = "accepted" if require_accepted else "draft"
    if route["route_status"] != expected_status:
        issues.append(f"route_status必须为{expected_status}")
    nodes = route["nodes"]
    if not isinstance(nodes, list) or not nodes:
        return issues + ["nodes必须是非空数组"]
    node_ids: list[str] = []
    successors: dict[str, list[str]] = {}
    predecessors: dict[str, list[str]] = {}
    ending_types: set[str] = set()
    for index, node in enumerate(nodes):
        label = f"nodes/{index}"
        if not exact_keys(node, NODE_FIELDS, label, issues):
            continue
        node_id = node["node_id"]
        if not isinstance(node_id, str) or EPISODE_ID.fullmatch(node_id) is None:
            issues.append(f"{label}/node_id非法")
            continue
        node_ids.append(node_id)
        if node["node_type"] != "episode":
            issues.append(f"{node_id}/node_type必须为episode")
        if not non_placeholder(node["分集标题"], 2):
            issues.append(f"{node_id}/分集标题为空或占位")
        material = node["route_material"]
        if exact_keys(material, MATERIAL_FIELDS, f"{node_id}/route_material", issues):
            if not non_placeholder(material["单集梗概"], 1):
                issues.append(f"{node_id}/单集梗概过短或占位")
            if not non_placeholder(material["本集冲突"], 1):
                issues.append(f"{node_id}/本集冲突过短或占位")
            if not non_placeholder(material["stop_boundary"], 1):
                issues.append(f"{node_id}/stop_boundary过短或占位")
            for state_field in ("entry_state", "state_changes"):
                if not isinstance(material[state_field], dict):
                    issues.append(f"{node_id}/{state_field}必须为对象")
            for asset_field in ("allowed_characters", "allowed_scenes", "allowed_props"):
                if not string_list(material[asset_field]) and material[asset_field] != []:
                    issues.append(f"{node_id}/{asset_field}必须是无重复字符串数组")
        prev = node["前置节点编号列表"]
        nxt = node["后续节点编号列表"]
        if not string_list(prev) and prev != []:
            issues.append(f"{node_id}/前置节点编号列表非法")
        if not string_list(nxt) and nxt != []:
            issues.append(f"{node_id}/后续节点编号列表非法")
        predecessors[node_id] = prev if isinstance(prev, list) else []
        successors[node_id] = nxt if isinstance(nxt, list) else []
        interaction = node["互动节点"]
        if exact_keys(interaction, INTERACTION_FIELDS, f"{node_id}/互动节点", issues):
            branch = interaction["是否为分支节点"]
            has_question = interaction["是否有选择问题"]
            options = interaction["选项列表"]
            if not isinstance(branch, bool) or not isinstance(has_question, bool) or branch != has_question:
                issues.append(f"{node_id}/分支布尔值错误")
            if not isinstance(options, list):
                issues.append(f"{node_id}/选项列表必须为数组")
                options = []
            for option_index, option in enumerate(options):
                exact_keys(option, OPTION_FIELDS, f"{node_id}/选项/{option_index}", issues)
            targets = [item.get("目标分集编号") for item in options if isinstance(item, dict)]
            numbers = [str(item.get("选项编号")) for item in options if isinstance(item, dict)]
            if branch:
                if not non_placeholder(interaction["选择问题"], 4) or len(set(targets)) < 2 or len(numbers) != len(set(numbers)):
                    issues.append(f"{node_id}/分支问题、编号或目标非法")
                if targets != nxt or interaction["默认下一分集编号"] not in targets:
                    issues.append(f"{node_id}/选项与后续或默认目标不一致")
            elif interaction["选择问题"] != "" or options:
                issues.append(f"{node_id}/非分支节点不得含选择")
        is_ending = node["是否结局"]
        if not isinstance(is_ending, bool):
            issues.append(f"{node_id}/是否结局必须为布尔值")
        elif is_ending:
            if node["ending_type"] not in ENDING_TYPES or nxt or interaction.get("默认下一分集编号") != "无":
                issues.append(f"{node_id}/结局字段不一致")
            else:
                ending_types.add(node["ending_type"])
        else:
            if node["ending_type"] is not None:
                issues.append(f"{node_id}/非结局ending_type必须为null")
            if not interaction.get("是否为分支节点") and (len(nxt) != 1 or interaction.get("默认下一分集编号") != (nxt[0] if nxt else None)):
                issues.append(f"{node_id}/普通节点必须有唯一默认后继")
        if require_accepted and node["node_route_material_hash"] != node_hash(node):
            issues.append(f"{node_id}/node_route_material_hash失效")
        elif not require_accepted and node["node_route_material_hash"] not in ("", None):
            issues.append(f"{node_id}/候选不得自填node_route_material_hash")
    expected_ids = [f"episode-{number:03d}" for number in range(1, len(node_ids) + 1)]
    if node_ids != expected_ids:
        issues.append("节点必须按稳定顺序连续编号")
    if len(set(node_ids)) != len(node_ids):
        issues.append("node_id重复")
    known = set(node_ids)
    for source in node_ids:
        for target in successors.get(source, []):
            if target not in known:
                issues.append(f"边目标不存在：{source}->{target}")
            elif source not in predecessors.get(target, []):
                issues.append(f"前后关系不对称：{source}->{target}")
        for parent in predecessors.get(source, []):
            if parent not in known or source not in successors.get(parent, []):
                issues.append(f"前后关系不对称：{parent}->{source}")
    entries = [node_id for node_id in node_ids if not predecessors.get(node_id)]
    if entries != ["episode-001"]:
        issues.append("流程图必须只有episode-001一个入口")
    visited: set[str] = set()
    active: set[str] = set()
    def walk(node_id: str) -> None:
        if node_id in active:
            issues.append(f"流程图存在环：{node_id}")
            return
        if node_id in visited:
            return
        active.add(node_id)
        for target in successors.get(node_id, []):
            if target in known:
                walk(target)
        active.remove(node_id)
        visited.add(node_id)
    if entries:
        walk(entries[0])
    if visited != known:
        issues.append(f"存在不可达节点：{sorted(known - visited)}")
    can_end = {node["node_id"] for node in nodes if isinstance(node, dict) and node.get("是否结局") is True}
    changed = True
    while changed:
        changed = False
        for source, targets in successors.items():
            if source not in can_end and any(target in can_end for target in targets):
                can_end.add(source); changed = True
    if can_end != known:
        issues.append(f"存在无法抵达结局的节点：{sorted(known - can_end)}")
    try:
        expected_edges, expected_choices, expected_endings = expected_indexes(nodes)
        if route["edges"] != expected_edges:
            issues.append("edges与节点连接不一致")
        if route["choices"] != expected_choices:
            issues.append("choices与互动节点不一致")
        if route["endings"] != expected_endings:
            issues.append("endings与结局节点不一致")
        for index, edge in enumerate(route["edges"]):
            exact_keys(edge, EDGE_FIELDS, f"edges/{index}", issues)
        for index, choice in enumerate(route["choices"]):
            exact_keys(choice, CHOICE_FIELDS, f"choices/{index}", issues)
        for index, ending in enumerate(route["endings"]):
            exact_keys(ending, ENDING_FIELDS, f"endings/{index}", issues)
    except (KeyError, TypeError):
        issues.append("路线索引不可解析")
    if require_accepted:
        try:
            accepted_time = datetime.fromisoformat(str(route["accepted_at"]).replace("Z", "+00:00"))
            if accepted_time.tzinfo is None:
                raise ValueError("missing timezone")
        except (TypeError, ValueError):
            issues.append("accepted_at必须是带时区ISO-8601")
        if route["route_output_hash"] != route_hash(route):
            issues.append("route_output_hash失效")
    elif route["route_output_hash"] not in ("", None) or route["accepted_at"] is not None:
        issues.append("候选路线不得自填验收哈希或时间")
    return list(dict.fromkeys(issues))


def seal(candidate: dict[str, Any], accepted_at: str | None = None) -> dict[str, Any]:
    issues = validate(candidate, require_accepted=False)
    if issues:
        raise ValueError("；".join(issues))
    route = deepcopy(candidate)
    route["route_status"] = "accepted"
    route["accepted_at"] = accepted_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for node in route["nodes"]:
        node["node_route_material_hash"] = node_hash(node)
    route["route_output_hash"] = route_hash(route)
    issues = validate(route, require_accepted=True)
    if issues:
        raise ValueError("；".join(issues))
    return route
