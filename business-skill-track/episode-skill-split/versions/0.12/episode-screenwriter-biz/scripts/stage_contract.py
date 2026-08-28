#!/usr/bin/env python3
"""Shared immutable contracts for the staged single-node writing chain."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from screenplay_contract import find_node

CONTEXT_VERSION = "nextplay.episode-screenwriting-context.v1"
PACKET_VERSION = "nextplay.node-writing-packet.v2"
RECEIPT_VERSION = "nextplay.compact-draft-receipt.v1"
CONTEXT_FIELDS = {
    "contract_version", "project_id", "route_id", "route_version", "route_output_hash",
    "node_id", "node_route_material_hash", "characters", "scenes", "props",
    "direct_predecessor_endings",
}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def names(items: Any) -> list[str] | None:
    if not isinstance(items, list):
        return None
    result = [item.get("name") for item in items if isinstance(item, dict)]
    if len(result) != len(items) or not all(nonempty(item) for item in result):
        return None
    return result


def context_issues(route: dict[str, Any], context: Any, node_id: str) -> list[str]:
    issues: list[str] = []
    node = find_node(route, node_id)
    if node is None:
        return ["ROUTE_DEPENDENCY_ERROR: 指定node_id不存在"]
    if not isinstance(context, dict) or set(context) != CONTEXT_FIELDS:
        return ["CONTEXT_DEPENDENCY_ERROR: 单节点写作上下文字段错误"]
    if context.get("contract_version") != CONTEXT_VERSION:
        issues.append("CONTEXT_DEPENDENCY_ERROR: 不支持的写作上下文合同")
    for field in ("project_id", "route_id", "route_version", "route_output_hash"):
        if context.get(field) != route.get(field):
            issues.append(f"CONTEXT_DEPENDENCY_ERROR: {field}与正式路线不一致")
    if context.get("node_id") != node_id:
        issues.append("CONTEXT_DEPENDENCY_ERROR: node_id不一致")
    if context.get("node_route_material_hash") != node.get("node_route_material_hash"):
        issues.append("CONTEXT_DEPENDENCY_ERROR: node_route_material_hash不一致")

    material = node.get("route_material") or {}
    entry_state = material.get("entry_state") or {}
    state_changes = material.get("state_changes") or {}
    pressure = entry_state.get("dramatic_pressure")
    effect = state_changes.get("dramatic_effect")
    if (pressure is None) != (effect is None):
        issues.append("ROUTE_DEPENDENCY_ERROR: 本集双因果压力与结果必须同时存在")
    elif pressure is not None:
        if not isinstance(pressure, dict) or set(pressure) != {"fact_trigger", "felt_meaning"} or not all(nonempty(value) for value in pressure.values()):
            issues.append("ROUTE_DEPENDENCY_ERROR: 本集双因果压力不完整")
        if not isinstance(effect, dict) or set(effect) != {"resulting_action", "human_change", "later_effect"} or not all(nonempty(value) for value in effect.values()):
            issues.append("ROUTE_DEPENDENCY_ERROR: 本集双因果结果不完整")
    for field, allowed_field in (("characters", "allowed_characters"), ("scenes", "allowed_scenes"), ("props", "allowed_props")):
        actual = names(context.get(field))
        expected = list(material.get(allowed_field) or [])
        if actual is None or len(actual) != len(set(actual)) or set(actual) != set(expected):
            issues.append(f"CONTEXT_DEPENDENCY_ERROR: {field}必须与节点白名单完全一致")

    for item in context.get("characters") or []:
        if not isinstance(item, dict):
            continue
        required = {"name", "public_identity", "identity_anchor", "current_relevance"}
        if not required.issubset(item) or not all(nonempty(item.get(field)) for field in required):
            issues.append(f"CONTEXT_DEPENDENCY_ERROR: 人物缺少公开身份或当前相关性：{item.get('name', '')}")
        extras = set(item) - {"name", "public_identity", "identity_anchor", "current_relevance", "relationship_context", "speech_profile"}
        if extras:
            issues.append(f"CONTEXT_DEPENDENCY_ERROR: 人物上下文含未知字段：{sorted(extras)}")
    for field in ("scenes", "props"):
        for item in context.get(field) or []:
            if not isinstance(item, dict) or set(item) != {"name", "public_description"} or not nonempty(item.get("public_description")):
                issues.append(f"CONTEXT_DEPENDENCY_ERROR: {field}缺少公开说明")
                break

    endings = context.get("direct_predecessor_endings")
    expected_predecessors = set(node.get("前置节点编号列表") or [])
    if not isinstance(endings, list):
        issues.append("CONTEXT_DEPENDENCY_ERROR: direct_predecessor_endings必须为数组")
    else:
        actual_predecessors: list[str] = []
        for item in endings:
            if not isinstance(item, dict) or set(item) != {"node_id", "ending_excerpt"} or not nonempty(item.get("node_id")) or not nonempty(item.get("ending_excerpt")):
                issues.append("CONTEXT_DEPENDENCY_ERROR: 直接前情结尾字段错误")
                continue
            actual_predecessors.append(item["node_id"])
        if len(actual_predecessors) != len(set(actual_predecessors)) or set(actual_predecessors) != expected_predecessors:
            issues.append("CONTEXT_DEPENDENCY_ERROR: 直接前情结尾与节点前置编号不一致")
    return list(dict.fromkeys(issues))


def build_packet(route: dict[str, Any], context: dict[str, Any], node_id: str) -> str:
    issues = context_issues(route, context, node_id)
    if issues:
        raise ValueError("；".join(issues))
    node = find_node(route, node_id)
    assert node is not None
    payload = {
        "binding": {
            "project_id": route["project_id"],
            "route_id": route["route_id"],
            "route_version": route["route_version"],
            "route_output_hash": route["route_output_hash"],
            "node_id": node_id,
            "node_route_material_hash": node["node_route_material_hash"],
        },
        "viewer_mode": "entry" if not (node.get("前置节点编号列表") or []) else "continuation",
        "route_material": node["route_material"],
        "branch_contract": node.get("互动节点") or {},
        "direct_predecessor_endings": context["direct_predecessor_endings"],
        "characters": context["characters"],
        "scenes": context["scenes"],
        "props": context["props"],
    }
    return f"WRITING_PACKET_VERSION={PACKET_VERSION}\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
