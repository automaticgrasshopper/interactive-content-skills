#!/usr/bin/env python3
"""Validate one screenplay patch against an immutable accepted route."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

ROUTE_VERSION = "nextplay.episode-route-handoff.v1"
ROUTE_CAPABILITY_ID = "episode-route-planner-biz"
ROUTE_SKILL_VERSION = "episode-route-planner-biz/0.01"
CONTRACT_VERSION = "nextplay.episode-node-patch.v1"
CAPABILITY_ID = "episode-screenwriter-biz"
SKILL_VERSION = "episode-screenwriter-biz/0.05"
PATCH_FIELDS = {
    "contract_version", "capability_id", "skill_version", "project_id", "route_id",
    "route_version", "route_output_hash", "node_id", "node_route_material_hash",
    "screenplay", "screenplay_hash", "status", "accepted_at",
}
SCREENPLAY_FIELDS = {
    "分集剧本", "剧本创作分析", "关联角色", "关联场景", "关联道具", "派生信息",
    "quality_checks",
}
ANALYSIS_FIELDS = {
    "创作分析", "场景和段落展开计划", "连续性分析", "冷读与质量问题", "验收结论",
}
CHECK_FIELDS = {"check", "passed", "evidence"}
REQUIRED_CHECKS = {"route_fidelity", "stop_boundary", "continuity", "dialogue", "asset_consistency"}
FORBIDDEN_PATCH_KEYS = {
    "nodes", "edges", "choices", "endings", "互动节点", "前置节点编号列表", "后续节点编号列表",
    "是否结局", "ending_type", "分集标题", "单集梗概", "本集冲突", "route_material", "stop_boundary",
}
SCENE = re.compile(r"【[^【】\n]+·[^【】\n]+·(?:内|外)】")
DIALOGUE = re.compile(r"(?m)^\s*[^\s：:【】]{1,20}：\s*\S+")
HASH = re.compile(r"[0-9a-f]{64}")
PLACEHOLDERS = {"占位", "待补", "待生成", "暂无", "tbd", "todo", "placeholder", "已检查", "符合要求"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


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


def screenplay_hash(patch: dict[str, Any]) -> str:
    return digest({
        "project_id": patch["project_id"],
        "route_id": patch["route_id"],
        "route_version": patch["route_version"],
        "route_output_hash": patch["route_output_hash"],
        "node_id": patch["node_id"],
        "node_route_material_hash": patch["node_route_material_hash"],
        "screenplay": patch["screenplay"],
    })


def exact(value: Any, fields: set[str], label: str, issues: list[str]) -> bool:
    if not isinstance(value, dict) or set(value) != fields:
        issues.append(f"{label}字段错误")
        return False
    return True


def meaningful(value: Any, minimum: int) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    return len(text) >= minimum and not any(term in lowered for term in PLACEHOLDERS)


def formal_route_issues(route: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(route, dict):
        return ["路线必须是JSON对象"]
    if route.get("contract_version") != ROUTE_VERSION:
        issues.append("ROUTE_DEPENDENCY_ERROR: 不支持的路线合同")
    if route.get("capability_id") != ROUTE_CAPABILITY_ID or route.get("skill_version") != ROUTE_SKILL_VERSION:
        issues.append("ROUTE_DEPENDENCY_ERROR: 路线生产者或版本不受支持")
    if route.get("route_status") != "accepted":
        issues.append("ROUTE_DEPENDENCY_ERROR: 路线未正式验收")
    if route.get("route_output_hash") != route_hash(route):
        issues.append("ROUTE_DEPENDENCY_ERROR: route_output_hash失效")
    nodes = route.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        issues.append("ROUTE_DEPENDENCY_ERROR: 路线没有节点")
        return issues
    for node in nodes:
        if not isinstance(node, dict) or node.get("node_route_material_hash") != node_hash(node):
            issues.append("ROUTE_DEPENDENCY_ERROR: 节点路线材料哈希失效")
            break
    return issues


def find_node(route: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in route.get("nodes") or []:
        if isinstance(node, dict) and node.get("node_id") == node_id:
            return node
    return None


def recursive_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(recursive_keys(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(recursive_keys(item) for item in value), set())
    return set()


def validate(route: Any, patch: Any, *, require_accepted: bool) -> list[str]:
    issues = formal_route_issues(route)
    if issues:
        return issues
    if not exact(patch, PATCH_FIELDS, "节点补丁", issues):
        return issues
    if patch["contract_version"] != CONTRACT_VERSION or patch["capability_id"] != CAPABILITY_ID:
        issues.append("节点补丁合同或能力标识错误")
    if patch["skill_version"] != SKILL_VERSION:
        issues.append("分集剧情Skill版本错误")
    for field in ("project_id", "route_id", "route_version", "route_output_hash"):
        if patch[field] != route.get(field):
            issues.append(f"ROUTE_DEPENDENCY_ERROR: {field}与正式路线不一致")
    node = find_node(route, str(patch["node_id"]))
    if node is None:
        issues.append("ROUTE_DEPENDENCY_ERROR: 指定node_id不存在")
        return issues
    if patch["node_route_material_hash"] != node.get("node_route_material_hash"):
        issues.append("ROUTE_DEPENDENCY_ERROR: node_route_material_hash不一致")
    screenplay = patch["screenplay"]
    if not exact(screenplay, SCREENPLAY_FIELDS, "screenplay", issues):
        return issues
    forbidden = recursive_keys(screenplay) & FORBIDDEN_PATCH_KEYS
    if forbidden:
        issues.append(f"节点补丁越权包含路线字段：{sorted(forbidden)}")
    script_block = screenplay["分集剧本"]
    if not exact(script_block, {"完整剧本"}, "分集剧本", issues):
        script = ""
    else:
        script = str(script_block["完整剧本"] or "").strip()
        if len(script) < 180 or SCENE.search(script) is None or DIALOGUE.search(script) is None:
            issues.append("完整剧本必须形成含场次、动作和对白的真实正文")
        if any(term in script.lower() for term in PLACEHOLDERS):
            issues.append("完整剧本含占位文字")
        if any(token in script for token in ("△", "出场：", "镜号", "运镜：", "景别：")):
            issues.append("完整剧本含禁止的制作标记")
    analysis = screenplay["剧本创作分析"]
    if exact(analysis, ANALYSIS_FIELDS, "剧本创作分析", issues):
        for field, minimum in (("创作分析", 24), ("场景和段落展开计划", 24), ("连续性分析", 24), ("冷读与质量问题", 24)):
            if not meaningful(analysis[field], minimum):
                issues.append(f"{field}过短或为抽象占位")
        if analysis["验收结论"] != "PASS":
            issues.append("验收结论必须为PASS")
    material = node.get("route_material") or {}
    for field, allowed_field in (("关联角色", "allowed_characters"), ("关联场景", "allowed_scenes"), ("关联道具", "allowed_props")):
        values = screenplay[field]
        allowed = set(material.get(allowed_field) or [])
        if not isinstance(values, list) or len(values) != len(set(values)) or not all(isinstance(item, str) and item in allowed for item in values):
            issues.append(f"{field}必须是允许白名单内的无重复字符串数组")
            continue
        missing = [item for item in values if item not in script]
        if missing:
            issues.append(f"{field}未在正文逐字出现：{missing}")
    if not isinstance(screenplay["派生信息"], dict):
        issues.append("派生信息必须为对象")
    checks = screenplay["quality_checks"]
    seen: set[str] = set()
    if not isinstance(checks, list):
        issues.append("quality_checks必须为数组")
    else:
        for index, check in enumerate(checks):
            if not exact(check, CHECK_FIELDS, f"quality_checks/{index}", issues):
                continue
            name = check["check"]
            seen.add(name)
            evidence = check["evidence"]
            if check["passed"] is not True or not isinstance(evidence, list) or not evidence:
                issues.append(f"quality_checks/{index}未通过或无证据")
            elif any(not meaningful(quote, 8) or str(quote) not in script for quote in evidence):
                issues.append(f"quality_checks/{index}证据必须逐字来自正文")
        if not REQUIRED_CHECKS.issubset(seen):
            issues.append(f"quality_checks缺少：{sorted(REQUIRED_CHECKS - seen)}")
    expected_status = "accepted" if require_accepted else "draft"
    if patch["status"] != expected_status:
        issues.append(f"status必须为{expected_status}")
    if require_accepted:
        if patch["screenplay_hash"] != screenplay_hash(patch):
            issues.append("screenplay_hash失效")
        try:
            accepted_time = datetime.fromisoformat(str(patch["accepted_at"]).replace("Z", "+00:00"))
            if accepted_time.tzinfo is None:
                raise ValueError("missing timezone")
        except (TypeError, ValueError):
            issues.append("accepted_at必须是带时区ISO-8601")
    elif patch["screenplay_hash"] not in ("", None) or patch["accepted_at"] is not None:
        issues.append("候选补丁不得自填验收哈希或时间")
    return list(dict.fromkeys(issues))


def seal(route: dict[str, Any], candidate: dict[str, Any], accepted_at: str | None = None) -> dict[str, Any]:
    issues = validate(route, candidate, require_accepted=False)
    if issues:
        raise ValueError("；".join(issues))
    patch = deepcopy(candidate)
    patch["status"] = "accepted"
    patch["accepted_at"] = accepted_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    patch["screenplay_hash"] = screenplay_hash(patch)
    issues = validate(route, patch, require_accepted=True)
    if issues:
        raise ValueError("；".join(issues))
    return patch
