#!/usr/bin/env python3
"""Build and slice a compact navigation index from an accepted episode route."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any


INDEX_VERSION = "nextplay.episode-plan-index.v1"
INDEX_FIELDS = {
    "contract_version", "project_id", "route_id", "route_version",
    "route_output_hash", "nodes", "index_hash",
}
NODE_FIELDS = {
    "node_id", "title", "summary", "conflict", "entry_state", "state_changes",
    "predecessors", "successors", "is_ending",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def build_index(route: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    for node in route.get("nodes") or []:
        material = node.get("route_material") or {}
        nodes.append({
            "node_id": node["node_id"],
            "title": node["分集标题"],
            "summary": material.get("单集梗概", ""),
            "conflict": material.get("本集冲突", ""),
            "entry_state": material.get("entry_state") or {},
            "state_changes": material.get("state_changes") or {},
            "predecessors": list(node.get("前置节点编号列表") or []),
            "successors": list(node.get("后续节点编号列表") or []),
            "is_ending": node.get("是否结局") is True,
        })
    value = {
        "contract_version": INDEX_VERSION,
        "project_id": route.get("project_id"),
        "route_id": route.get("route_id"),
        "route_version": route.get("route_version"),
        "route_output_hash": route.get("route_output_hash"),
        "nodes": nodes,
        "index_hash": "",
    }
    value["index_hash"] = index_hash(value)
    return value


def index_hash(index: dict[str, Any]) -> str:
    value = dict(index)
    value.pop("index_hash", None)
    return digest(value)


def validate_index(route: dict[str, Any], index: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(index, dict) or set(index) != INDEX_FIELDS:
        return ["单集计划索引字段错误"]
    if index.get("contract_version") != INDEX_VERSION:
        issues.append("单集计划索引合同错误")
    for field in ("project_id", "route_id", "route_version", "route_output_hash"):
        if index.get(field) != route.get(field):
            issues.append(f"单集计划索引的{field}与正式路线不一致")
    nodes = index.get("nodes")
    if not isinstance(nodes, list):
        issues.append("单集计划索引nodes必须为数组")
        nodes = []
    for position, node in enumerate(nodes):
        if not isinstance(node, dict) or set(node) != NODE_FIELDS:
            issues.append(f"单集计划索引nodes/{position}字段错误")
    expected = build_index(route)
    if nodes != expected["nodes"]:
        issues.append("单集计划索引未由当前正式路线生成")
    if index.get("index_hash") != index_hash(index):
        issues.append("单集计划索引哈希失效")
    return list(dict.fromkeys(issues))


def planned_causality(node: dict[str, Any]) -> dict[str, str] | None:
    pressure = (node.get("entry_state") or {}).get("dramatic_pressure")
    effect = (node.get("state_changes") or {}).get("dramatic_effect")
    if not isinstance(pressure, dict) or not isinstance(effect, dict):
        return None
    return {
        "fact_trigger": str(pressure.get("fact_trigger") or "").strip(),
        "felt_meaning": str(pressure.get("felt_meaning") or "").strip(),
        "resulting_action": str(effect.get("resulting_action") or "").strip(),
        "human_change": str(effect.get("human_change") or "").strip(),
        "later_effect": str(effect.get("later_effect") or "").strip(),
    }


def nearest_human_turns(start: str, by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    visited: set[str] = set()
    found_depth: int | None = None
    found: list[dict[str, Any]] = []
    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited or (found_depth is not None and depth > found_depth):
            continue
        visited.add(node_id)
        node = by_id.get(node_id)
        if node is None:
            continue
        causality = planned_causality(node)
        if causality is not None:
            found_depth = depth
            found.append({
                "node_id": node_id,
                "title": node["title"],
                "planned_causality": causality,
            })
            continue
        for successor in node["successors"]:
            queue.append((successor, depth + 1))
    return found


def navigation_slice(route: dict[str, Any], index: dict[str, Any], node_id: str) -> dict[str, Any]:
    issues = validate_index(route, index)
    if issues:
        raise ValueError("；".join(issues))
    by_id = {node["node_id"]: node for node in index["nodes"]}
    current = by_id.get(node_id)
    if current is None:
        raise ValueError("单集计划索引中不存在当前节点")
    next_plans = []
    later_turns = []
    for successor in current["successors"]:
        next_node = by_id[successor]
        next_plans.append({
            "node_id": successor,
            "title": next_node["title"],
            "summary": next_node["summary"],
            "conflict": next_node["conflict"],
            "planned_state_changes": next_node["state_changes"],
        })
        for turn in nearest_human_turns(successor, by_id):
            item = {"from_successor": successor, **turn}
            if item not in later_turns:
                later_turns.append(item)
    return {
        "graph_overview": [
            {
                "node_id": node["node_id"],
                "title": node["title"],
                "successors": node["successors"],
                "is_ending": node["is_ending"],
            }
            for node in index["nodes"]
        ],
        "next_node_plans": next_plans,
        "next_human_turns": later_turns,
        "usage": "只用于理解当前节点在整集中的位置和铺垫方向；不得复述这些文字，不得提前演出后续节点。",
    }
