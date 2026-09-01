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
CONTRACT_VERSION = "nextplay.episode-node-patch.v1"
CAPABILITY_ID = "episode-screenwriter-biz"
PATCH_FIELDS = {
    "contract_version", "capability_id", "project_id", "route_id",
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
DERIVED_DRAFT_FIELDS = {"character_deltas", "relationship_deltas", "shared_memories"}
DERIVED_ACCEPTED_FIELDS = DERIVED_DRAFT_FIELDS | {"state_snapshot"}
CHARACTER_DELTA_FIELDS = {
    "character", "axis", "before", "after", "behavioral_effect", "authority", "evidence",
}
RELATIONSHIP_DELTA_FIELDS = {
    "source", "target", "dimension", "before", "after", "behavioral_effect", "authority", "evidence",
}
MEMORY_FIELDS = {"participants", "memory", "future_use", "evidence"}
STATE_FIELDS = {"characters", "relationships", "shared_memories"}
CHARACTER_STATE_FIELDS = {"character", "axis", "current_state", "behavioral_effect", "source_node"}
RELATIONSHIP_STATE_FIELDS = {
    "source", "target", "dimension", "current_state", "behavioral_effect", "source_node",
}
MEMORY_STATE_FIELDS = {"participants", "memory", "future_use", "source_node"}
CHARACTER_AXES = {"goal", "belief", "self_view", "strategy", "boundary"}
RELATIONSHIP_DIMENSIONS = {
    "trust", "openness", "alignment", "power", "attachment", "commitment", "boundary",
}
AUTHORITIES = {"route_locked", "screenplay_observed"}
REQUIRED_CHECKS = {
    "route_fidelity", "stop_boundary", "continuity", "first_appearance",
    "spatial_continuity", "prose_dramatization", "asset_consistency",
}
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


def meaningful(value: Any) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    return bool(text) and not any(term in lowered for term in PLACEHOLDERS)


def action_blocks(script: str) -> list[str]:
    blocks = [item.strip() for item in re.split(r"\n\s*\n", script.strip()) if item.strip()]
    return [item for item in blocks if SCENE.fullmatch(item) is None and DIALOGUE.fullmatch(item) is None]


def empty_state_snapshot() -> dict[str, list[dict[str, Any]]]:
    return {"characters": [], "relationships": [], "shared_memories": []}


def state_snapshot_issues(value: Any, label: str = "state_snapshot") -> list[str]:
    issues: list[str] = []
    if not exact(value, STATE_FIELDS, label, issues):
        return issues
    for index, item in enumerate(value["characters"] if isinstance(value["characters"], list) else []):
        if not exact(item, CHARACTER_STATE_FIELDS, f"{label}/characters/{index}", issues):
            continue
        if item["axis"] not in CHARACTER_AXES or not all(meaningful(item[field]) for field in CHARACTER_STATE_FIELDS):
            issues.append(f"{label}/characters/{index}内容非法")
    if not isinstance(value["characters"], list):
        issues.append(f"{label}/characters必须为数组")
    for index, item in enumerate(value["relationships"] if isinstance(value["relationships"], list) else []):
        if not exact(item, RELATIONSHIP_STATE_FIELDS, f"{label}/relationships/{index}", issues):
            continue
        if item["source"] == item["target"] or item["dimension"] not in RELATIONSHIP_DIMENSIONS or not all(meaningful(item[field]) for field in RELATIONSHIP_STATE_FIELDS):
            issues.append(f"{label}/relationships/{index}内容非法")
    if not isinstance(value["relationships"], list):
        issues.append(f"{label}/relationships必须为数组")
    for index, item in enumerate(value["shared_memories"] if isinstance(value["shared_memories"], list) else []):
        if not exact(item, MEMORY_STATE_FIELDS, f"{label}/shared_memories/{index}", issues):
            continue
        participants = item["participants"]
        if (
            not isinstance(participants, list) or not participants
            or len(participants) != len(set(participants))
            or not all(meaningful(name) for name in participants)
            or not all(meaningful(item[field]) for field in ("memory", "future_use", "source_node"))
        ):
            issues.append(f"{label}/shared_memories/{index}内容非法")
    if not isinstance(value["shared_memories"], list):
        issues.append(f"{label}/shared_memories必须为数组")
    return list(dict.fromkeys(issues))


def derived_info_issues(
    value: Any,
    script: str,
    allowed_characters: set[str],
    *,
    require_accepted: bool,
) -> list[str]:
    issues: list[str] = []
    expected = DERIVED_ACCEPTED_FIELDS if require_accepted else DERIVED_DRAFT_FIELDS
    if not exact(value, expected, "派生信息", issues):
        return issues
    for index, item in enumerate(value["character_deltas"] if isinstance(value["character_deltas"], list) else []):
        if not exact(item, CHARACTER_DELTA_FIELDS, f"派生信息/character_deltas/{index}", issues):
            continue
        if item["character"] not in allowed_characters or item["axis"] not in CHARACTER_AXES:
            issues.append(f"派生信息/character_deltas/{index}人物或轴非法")
        if item["authority"] not in AUTHORITIES or item["before"] == item["after"]:
            issues.append(f"派生信息/character_deltas/{index}变化无效")
        if not all(meaningful(item[field]) for field in CHARACTER_DELTA_FIELDS):
            issues.append(f"派生信息/character_deltas/{index}内容为空")
        elif item["evidence"] not in script:
            issues.append(f"派生信息/character_deltas/{index}证据不在正文")
    if not isinstance(value["character_deltas"], list):
        issues.append("派生信息/character_deltas必须为数组")
    for index, item in enumerate(value["relationship_deltas"] if isinstance(value["relationship_deltas"], list) else []):
        if not exact(item, RELATIONSHIP_DELTA_FIELDS, f"派生信息/relationship_deltas/{index}", issues):
            continue
        if item["source"] not in allowed_characters or item["target"] not in allowed_characters or item["source"] == item["target"]:
            issues.append(f"派生信息/relationship_deltas/{index}人物非法")
        if item["dimension"] not in RELATIONSHIP_DIMENSIONS or item["authority"] not in AUTHORITIES or item["before"] == item["after"]:
            issues.append(f"派生信息/relationship_deltas/{index}变化无效")
        if not all(meaningful(item[field]) for field in RELATIONSHIP_DELTA_FIELDS):
            issues.append(f"派生信息/relationship_deltas/{index}内容为空")
        elif item["evidence"] not in script:
            issues.append(f"派生信息/relationship_deltas/{index}证据不在正文")
    if not isinstance(value["relationship_deltas"], list):
        issues.append("派生信息/relationship_deltas必须为数组")
    for index, item in enumerate(value["shared_memories"] if isinstance(value["shared_memories"], list) else []):
        if not exact(item, MEMORY_FIELDS, f"派生信息/shared_memories/{index}", issues):
            continue
        participants = item["participants"]
        if (
            not isinstance(participants, list) or not participants
            or len(participants) != len(set(participants))
            or not set(participants).issubset(allowed_characters)
        ):
            issues.append(f"派生信息/shared_memories/{index}人物非法")
        if not all(meaningful(item[field]) for field in ("memory", "future_use", "evidence")):
            issues.append(f"派生信息/shared_memories/{index}内容为空")
        elif item["evidence"] not in script:
            issues.append(f"派生信息/shared_memories/{index}证据不在正文")
    if not isinstance(value["shared_memories"], list):
        issues.append("派生信息/shared_memories必须为数组")
    if require_accepted:
        issues.extend(state_snapshot_issues(value["state_snapshot"], "派生信息/state_snapshot"))
    return list(dict.fromkeys(issues))


def fold_state_snapshot(
    prior: dict[str, Any] | None,
    derived: dict[str, Any],
    node_id: str,
) -> dict[str, list[dict[str, Any]]]:
    base = deepcopy(prior) if prior is not None else empty_state_snapshot()
    issues = state_snapshot_issues(base)
    if issues:
        raise ValueError("；".join(issues))
    characters = {(item["character"], item["axis"]): item for item in base["characters"]}
    relationships = {
        (item["source"], item["target"], item["dimension"]): item
        for item in base["relationships"]
    }
    memories = {
        (tuple(item["participants"]), item["memory"]): item
        for item in base["shared_memories"]
    }
    for item in derived["character_deltas"]:
        characters[(item["character"], item["axis"])] = {
            "character": item["character"],
            "axis": item["axis"],
            "current_state": item["after"],
            "behavioral_effect": item["behavioral_effect"],
            "source_node": node_id,
        }
    for item in derived["relationship_deltas"]:
        relationships[(item["source"], item["target"], item["dimension"])] = {
            "source": item["source"],
            "target": item["target"],
            "dimension": item["dimension"],
            "current_state": item["after"],
            "behavioral_effect": item["behavioral_effect"],
            "source_node": node_id,
        }
    for item in derived["shared_memories"]:
        memories[(tuple(item["participants"]), item["memory"])] = {
            "participants": item["participants"],
            "memory": item["memory"],
            "future_use": item["future_use"],
            "source_node": node_id,
        }
    return {
        "characters": list(characters.values()),
        "relationships": list(relationships.values()),
        "shared_memories": list(memories.values()),
    }


def formal_route_issues(route: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(route, dict):
        return ["路线必须是JSON对象"]
    if route.get("contract_version") != ROUTE_VERSION:
        issues.append("ROUTE_DEPENDENCY_ERROR: 不支持的路线合同")
    if route.get("capability_id") != ROUTE_CAPABILITY_ID:
        issues.append("ROUTE_DEPENDENCY_ERROR: 路线生产者不受支持")
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
        material = node.get("route_material") or {}
        entry_state = material.get("entry_state") or {}
        state_changes = material.get("state_changes") or {}
        pressure = entry_state.get("dramatic_pressure")
        effect = state_changes.get("dramatic_effect")
        if (pressure is None) != (effect is None):
            issues.append("ROUTE_DEPENDENCY_ERROR: 节点双因果压力与结果必须同时存在")
            break
        if pressure is not None:
            if not isinstance(pressure, dict) or set(pressure) != {"fact_trigger", "felt_meaning"} or not all(meaningful(value) for value in pressure.values()):
                issues.append("ROUTE_DEPENDENCY_ERROR: 节点双因果压力不完整")
                break
            if not isinstance(effect, dict) or set(effect) != {"resulting_action", "human_change", "later_effect"} or not all(meaningful(value) for value in effect.values()):
                issues.append("ROUTE_DEPENDENCY_ERROR: 节点双因果结果不完整")
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
        if SCENE.search(script) is None or not action_blocks(script):
            issues.append("完整剧本必须形成含场次和实际动作的真实正文")
        if any(term in script.lower() for term in PLACEHOLDERS):
            issues.append("完整剧本含占位文字")
        if any(token in script for token in ("△", "出场：", "镜号", "运镜：", "景别：")):
            issues.append("完整剧本含禁止的制作标记")
    analysis = screenplay["剧本创作分析"]
    if exact(analysis, ANALYSIS_FIELDS, "剧本创作分析", issues):
        for field in ("创作分析", "场景和段落展开计划", "连续性分析", "冷读与质量问题"):
            if not meaningful(analysis[field]):
                issues.append(f"{field}为空或为抽象占位")
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
    issues.extend(
        derived_info_issues(
            screenplay["派生信息"],
            script,
            set(material.get("allowed_characters") or []),
            require_accepted=require_accepted,
        )
    )
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
            elif any(not meaningful(quote) or str(quote) not in script for quote in evidence):
                issues.append(f"quality_checks/{index}证据必须逐字来自正文")
        required_checks = set(REQUIRED_CHECKS)
        entry_state = material.get("entry_state") or {}
        state_changes = material.get("state_changes") or {}
        if entry_state.get("dramatic_pressure") is not None and state_changes.get("dramatic_effect") is not None:
            required_checks.add("dramatic_causality")
        if DIALOGUE.search(script):
            required_checks.add("dialogue")
        interaction = node.get("互动节点") or {}
        options = interaction.get("选项列表") or []
        if interaction.get("是否为分支节点") is True:
            required_checks.add("choice_readiness")
            choice_checks = [item for item in checks if isinstance(item, dict) and item.get("check") == "choice_readiness"]
            if choice_checks:
                evidence = choice_checks[0].get("evidence")
                if not isinstance(evidence, list) or len(evidence) < len(options) or len(evidence) != len(set(evidence)):
                    issues.append("choice_readiness必须为每个冻结选项提供不同正文证据")
        if not required_checks.issubset(seen):
            issues.append(f"quality_checks缺少：{sorted(required_checks - seen)}")
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


def seal(
    route: dict[str, Any],
    candidate: dict[str, Any],
    accepted_at: str | None = None,
    prior_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues = validate(route, candidate, require_accepted=False)
    if issues:
        raise ValueError("；".join(issues))
    patch = deepcopy(candidate)
    derived = patch["screenplay"]["派生信息"]
    derived["state_snapshot"] = fold_state_snapshot(prior_state, derived, patch["node_id"])
    patch["status"] = "accepted"
    patch["accepted_at"] = accepted_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    patch["screenplay_hash"] = screenplay_hash(patch)
    issues = validate(route, patch, require_accepted=True)
    if issues:
        raise ValueError("；".join(issues))
    return patch
