#!/usr/bin/env python3
"""Validate machine bindings and project them into clean creative materials."""

from __future__ import annotations

import hashlib
from typing import Any

from screenplay_contract import find_node

CONTEXT_VERSION = "nextplay.episode-screenwriting-context.v1"
PACKET_HEADER = "# 单集写作材料\n"
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


def optional_line(label: str, value: Any) -> str | None:
    text = str(value or "").strip()
    return f"- {label}：{text}" if text else None


def build_packet(route: dict[str, Any], context: dict[str, Any], node_id: str) -> str:
    issues = context_issues(route, context, node_id)
    if issues:
        raise ValueError("；".join(issues))
    node = find_node(route, node_id)
    assert node is not None
    material = node["route_material"]
    pressure = (material.get("entry_state") or {}).get("dramatic_pressure")
    effect = (material.get("state_changes") or {}).get("dramatic_effect")
    predecessors = context["direct_predecessor_endings"]
    interaction = node.get("互动节点") or {}

    lines = [
        "# 单集写作材料",
        "",
        "## 当前任务",
        "",
        f"把《{node['分集标题']}》写成一集完整、可拍的剧本，只表达本页已经冻结的事实。",
        "",
        "## 本集剧情",
        "",
        f"- 梗概：{material['单集梗概']}",
        f"- 核心冲突：{material['本集冲突']}",
        "",
        "## 人物行动因果",
        "",
    ]
    if pressure is not None and effect is not None:
        lines.extend([
            f"- 外部压力：{pressure['fact_trigger']}",
            f"- 人物怎样理解：{pressure['felt_meaning']}",
            f"- 因此采取的行动：{effect['resulting_action']}",
            f"- 人物或关系发生的变化：{effect['human_change']}",
            f"- 留给后续行为的约束：{effect['later_effect']}",
        ])
    else:
        lines.append("- 本集只完成事实过桥，不新增人物创伤、关系转折或情绪任务。")

    lines.extend(["", "## 观看入口与结束位置", ""])
    if predecessors:
        lines.append("- 这是续接集，只承接下面列出的直接前情，不重复首集建制。")
    else:
        lines.append("- 这是入口集；观众理解必须附着在第一轮真正改变局面的行动中。")
    lines.append(f"- 结束位置：{material['stop_boundary']}")

    lines.extend(["", "## 互动边界", ""])
    if interaction.get("是否为分支节点") is True:
        lines.append(f"- 当前决定：{interaction.get('选择问题', '')}")
        lines.append("- 本集只让以下动作在现场变得可执行，不执行动作，也不演出其后果：")
        for option in interaction.get("选项列表") or []:
            lines.append(f"  - {option['选项文字']}")
    else:
        lines.append("- 本集不是选择来源，不制造额外选择感。")

    lines.extend(["", "## 直接前情", ""])
    if predecessors:
        for item in predecessors:
            lines.append(f"- {item['ending_excerpt']}")
    else:
        lines.append("- 无直接前情。")

    lines.extend(["", "## 可用人物", ""])
    for character in context["characters"]:
        lines.extend([
            f"### {character['name']}",
            "",
            f"- 公开身份：{character['public_identity']}",
            f"- 当前为什么在场：{character['current_relevance']}",
        ])
        for line in (
            optional_line("当前关系", character.get("relationship_context")),
            optional_line("说话方式", character.get("speech_profile")),
        ):
            if line:
                lines.append(line)
        lines.append("")

    lines.extend(["## 可用场景", ""])
    for scene in context["scenes"]:
        lines.append(f"- {scene['name']}：{scene['public_description']}")

    lines.extend(["", "## 可用道具", ""])
    if context["props"]:
        for prop in context["props"]:
            lines.append(f"- {prop['name']}：{prop['public_description']}")
    else:
        lines.append("- 本集没有登记道具。")

    lines.extend([
        "",
        "## 写作边界",
        "",
        "- 不增加本页之外的人物、场景、道具、规则、证据来源、设备机制或未来事件。",
        "- 不修改标题、剧情连接、选择、结局、资产范围或结束位置。",
        "- 内部分析词只用于理解，正文必须写成观众可见可听的动作与人话。",
    ])
    return "\n".join(lines).rstrip() + "\n"
