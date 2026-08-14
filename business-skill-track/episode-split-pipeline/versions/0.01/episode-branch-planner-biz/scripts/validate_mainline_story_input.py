#!/usr/bin/env python3
"""Validate the six-group creative input used only for the readable mainline story."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from build_stage_two_input import validate_frozen as validate_stage_two_input


CONTRACT_VERSION = "nextplay.mainline-story-input.v1"
ROOT_FIELDS = {
    "contract_version", "stage_two_input_sha256", "title", "core_event",
    "story_boundaries", "required_story_facts", "essential_assets", "expected_payoff",
}
CORE_FIELDS = {"protagonist", "inciting_event", "goal", "opposition", "stakes"}
ASSET_FIELDS = {"characters", "scenes", "props"}
CHARACTER_FIELDS = {"name", "public_role", "current_motive", "key_relationship"}
FUNCTION_FIELDS = {"name", "story_function"}
PAYOFF_FIELDS = {"genre", "tone", "ending_direction"}
STRUCTURE_MARKERS = (
    "node_count_hint", "interaction_min", "interaction_max", "分集数量",
    "节点数量", "拓扑形状", "开扇比例",
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def text(value: Any, label: str, issues: list[str], minimum: int = 2) -> str:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        issues.append(f"第一版故事输入缺少可读字段：{label}")
        return ""
    return value.strip()


def text_list(value: Any, label: str, issues: list[str], *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        issues.append(f"第一版故事输入列表无效：{label}")
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or len(item.strip()) < 4:
            issues.append(f"第一版故事输入列表含无效内容：{label}")
            continue
        result.append(item.strip())
    if len(result) != len(set(result)):
        issues.append(f"第一版故事输入列表存在重复：{label}")
    return result


def available_names(stage_two: dict[str, Any], kind: str) -> set[str]:
    assets = stage_two.get("assets") if isinstance(stage_two.get("assets"), dict) else {}
    values = assets.get(kind)
    return {item.strip() for item in values if isinstance(item, str) and item.strip()} if isinstance(values, list) else set()


def validate(cache_root: Path) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    stage_two = validate_stage_two_input(cache_root)
    path = cache_root / "mainline-story-input.json"
    if not path.is_file():
        return {}, ["缺少第一版故事六组输入：mainline-story-input.json"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, [f"第一版故事输入不可读取：{error}"]
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        return {}, ["第一版故事输入根字段错误，必须只含六组创作信息及合同指纹"]
    if data.get("contract_version") != CONTRACT_VERSION:
        issues.append(f"第一版故事输入合同错误：期望 {CONTRACT_VERSION}")
    if data.get("stage_two_input_sha256") != digest(stage_two):
        issues.append("第一版故事输入未绑定当前阶段二输入")

    text(data.get("title"), "title", issues)
    if data.get("title") != stage_two.get("story", {}).get("title"):
        issues.append("第一版故事标题必须逐字使用冻结标题")
    core = data.get("core_event")
    if not isinstance(core, dict) or set(core) != CORE_FIELDS:
        issues.append("core_event必须只含主角、触发事件、目标、阻力和失败代价")
        core = {}
    for field in CORE_FIELDS:
        text(core.get(field), f"core_event.{field}", issues, 4)
    if core.get("goal") != stage_two.get("story", {}).get("core_goal"):
        issues.append("第一版故事核心目标必须逐字使用冻结目标")

    boundaries = text_list(data.get("story_boundaries"), "story_boundaries", issues)
    boundary_corpus = "\n".join(boundaries)
    source_story = stage_two.get("story", {}) if isinstance(stage_two.get("story"), dict) else {}
    for field in ("world_rules", "safety_constraints", "consistency_constraints"):
        source_values = source_story.get(field)
        for required in source_values if isinstance(source_values, list) else []:
            if required not in boundary_corpus:
                issues.append(f"第一版故事边界遗漏冻结约束：{required}")
    facts = text_list(data.get("required_story_facts"), "required_story_facts", issues)
    source_required = stage_two.get("story", {}).get("required_events", [])
    for required in source_required if isinstance(source_required, list) else []:
        if required not in facts:
            issues.append(f"第一版故事输入遗漏上游必保事实：{required}")

    essential = data.get("essential_assets")
    if not isinstance(essential, dict) or set(essential) != ASSET_FIELDS:
        issues.append("essential_assets必须只含characters/scenes/props")
        essential = {}
    for kind, fields, allow_empty in (
        ("characters", CHARACTER_FIELDS, False),
        ("scenes", FUNCTION_FIELDS, False),
        ("props", FUNCTION_FIELDS, True),
    ):
        entries = essential.get(kind)
        if not isinstance(entries, list) or (not allow_empty and not entries):
            issues.append(f"essential_assets.{kind}无效")
            continue
        names: list[str] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or set(entry) != fields:
                issues.append(f"essential_assets.{kind}[{index}]字段错误")
                continue
            name = text(entry.get("name"), f"essential_assets.{kind}[{index}].name", issues)
            if name:
                names.append(name)
            for field in fields - {"name", "key_relationship"}:
                text(entry.get(field), f"essential_assets.{kind}[{index}].{field}", issues, 4)
            if "key_relationship" in fields and entry.get("key_relationship") is not None:
                text(entry.get("key_relationship"), f"essential_assets.{kind}[{index}].key_relationship", issues, 4)
        if len(names) != len(set(names)):
            issues.append(f"essential_assets.{kind}存在重名")
        unknown = set(names) - available_names(stage_two, kind)
        if unknown:
            issues.append(f"essential_assets.{kind}含非正式资产：{sorted(unknown)}")

    payoff = data.get("expected_payoff")
    if not isinstance(payoff, dict) or set(payoff) != PAYOFF_FIELDS:
        issues.append("expected_payoff必须只含genre/tone/ending_direction")
        payoff = {}
    for field in PAYOFF_FIELDS:
        text(payoff.get(field), f"expected_payoff.{field}", issues, 4)
    directions = stage_two.get("ending_plan", {}).get("directions", [])
    if payoff.get("ending_direction") not in directions:
        issues.append("期待性结局方向必须逐字选自冻结结局计划")

    serialized = json.dumps(data, ensure_ascii=False)
    leaked = [marker for marker in STRUCTURE_MARKERS if marker in serialized]
    if leaked:
        issues.append("第一版故事六组输入泄露后续结构信息：" + "、".join(leaked))
    if not boundaries:
        issues.append("第一版故事至少需要一条有效边界")
    return data, list(dict.fromkeys(issues))


def validate_frozen(cache_root: Path) -> dict[str, Any]:
    data, issues = validate(cache_root)
    if issues:
        raise ValueError("；".join(issues))
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        _, issues = validate(args.cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues = [str(error)]
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: readable mainline is isolated to six creative input groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
