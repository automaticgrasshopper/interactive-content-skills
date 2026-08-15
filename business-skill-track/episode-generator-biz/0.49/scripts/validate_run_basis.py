#!/usr/bin/env python3
"""Validate the private stage-one freeze before topology work begins."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_character_appearances import (
    INTRODUCTION_VERSION,
    load_asset_catalog,
)
from validate_user_intent_lock import validate_contract


BASIS_VERSION = "nextplay.episode-run-basis.v2"


def nonempty(value: Any, label: str, issues: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        issues.append(f"运行基础缺少非空字段：{label}")
        return ""
    return value.strip()


def string_list(
    value: Any,
    label: str,
    issues: list[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        issues.append(f"运行基础字段必须是列表：{label}")
        return []
    if not allow_empty and not value:
        issues.append(f"运行基础列表不得为空：{label}")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        issues.append(f"运行基础列表含空值：{label}")
        return []
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        issues.append(f"运行基础列表存在重复项：{label}")
    return normalized


def load_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少{label}：{path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须是对象")
    return value


def validate_basis(
    cache_root: Path,
    *,
    require_empty_introductions: bool = False,
) -> list[str]:
    issues: list[str] = []
    _, _, intent_issues = validate_contract(cache_root)
    issues.extend(intent_issues)
    try:
        catalog = load_asset_catalog(cache_root / "asset-catalog.json")
        basis = load_object(cache_root / "run-basis.json", "运行基础")
        introductions = load_object(
            cache_root / "character-introductions.json",
            "角色首次出场登记",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return list(dict.fromkeys([*issues, str(error)]))

    if basis.get("contract_version") != BASIS_VERSION:
        issues.append(f"运行基础合同错误：期望 {BASIS_VERSION}")
    if set(basis) != {"contract_version", "story", "ending_plan", "characters"}:
        issues.append("run-basis.json 顶层字段错误")

    story = basis.get("story")
    expected_story = {
        "title",
        "core_goal",
        "core_conflict",
        "theme",
        "genre_tone",
        "world_rules",
        "duration",
        "node_count_hint",
        "required_events",
        "safety_constraints",
        "consistency_constraints",
    }
    if not isinstance(story, dict) or set(story) != expected_story:
        issues.append("run-basis.json story 字段错误")
        story = {}
    for key in (
        "title",
        "core_goal",
        "core_conflict",
        "theme",
        "genre_tone",
    ):
        nonempty(story.get(key), f"story.{key}", issues)
    duration = story.get("duration")
    if duration is not None and (
        not isinstance(duration, str) or not duration.strip()
    ):
        issues.append("story.duration 必须是非空来源文本或 null")
    string_list(story.get("world_rules"), "story.world_rules", issues)
    string_list(
        story.get("required_events"),
        "story.required_events",
        issues,
        allow_empty=True,
    )
    string_list(
        story.get("safety_constraints"),
        "story.safety_constraints",
        issues,
        allow_empty=True,
    )
    string_list(
        story.get("consistency_constraints"),
        "story.consistency_constraints",
        issues,
        allow_empty=True,
    )
    hint = story.get("node_count_hint")
    if hint is not None and (
        isinstance(hint, bool)
        or not isinstance(hint, (int, str))
        or (isinstance(hint, int) and hint < 1)
        or (isinstance(hint, str) and not hint.strip())
    ):
        issues.append("story.node_count_hint 必须是正整数、非空区间文本或 null")

    plan = basis.get("ending_plan")
    if not isinstance(plan, dict) or set(plan) != {
        "total",
        "formal",
        "failure",
        "directions",
    }:
        issues.append("run-basis.json ending_plan 字段错误")
        plan = {}
    counts: dict[str, int] = {}
    for key in ("total", "formal", "failure"):
        value = plan.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            issues.append(f"ending_plan.{key} 必须是非负整数")
        else:
            counts[key] = value
    if counts.get("total", 0) < 1:
        issues.append("ending_plan.total 必须大于0")
    if counts.get("total") != counts.get("formal", -1) + counts.get("failure", -1):
        issues.append("ending_plan.total 必须等于 formal + failure")
    directions = string_list(
        plan.get("directions"),
        "ending_plan.directions",
        issues,
    )
    if "total" in counts and len(directions) != counts["total"]:
        issues.append("ending_plan.directions 数量必须等于 total")

    characters = basis.get("characters")
    if not isinstance(characters, list) or not characters:
        issues.append("run-basis.json characters 必须是非空数组")
        characters = []
    names: list[str] = []
    expected_character_fields = {
        "name",
        "identity",
        "relationships",
        "current_desire",
        "knowledge_boundary",
        "capability_boundary",
        "voice",
    }
    for index, character in enumerate(characters):
        if not isinstance(character, dict) or set(character) != expected_character_fields:
            issues.append(f"运行角色第{index + 1}项字段错误")
            continue
        name = nonempty(character.get("name"), f"characters[{index}].name", issues)
        if name:
            names.append(name)
        nonempty(character.get("identity"), f"characters[{index}].identity", issues)
        string_list(
            character.get("relationships"),
            f"characters[{index}].relationships",
            issues,
        )
        nonempty(
            character.get("current_desire"),
            f"characters[{index}].current_desire",
            issues,
        )
        string_list(
            character.get("knowledge_boundary"),
            f"characters[{index}].knowledge_boundary",
            issues,
        )
        string_list(
            character.get("capability_boundary"),
            f"characters[{index}].capability_boundary",
            issues,
        )
        nonempty(character.get("voice"), f"characters[{index}].voice", issues)
    if len(names) != len(set(names)):
        issues.append("run-basis.json characters 存在重名")
    if set(names) != catalog["characters"]:
        issues.append("run-basis.json 角色集合必须与 asset-catalog.json 完全一致")

    if introductions.get("contract_version") != INTRODUCTION_VERSION:
        issues.append(f"角色首次出场合同错误：期望 {INTRODUCTION_VERSION}")
    entries = introductions.get("characters")
    if not isinstance(entries, list):
        issues.append("character-introductions.json characters 必须是数组")
    else:
        entry_names: list[str] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or set(entry) != {"name", "introductions"}:
                issues.append(f"character-introductions 第{index + 1}项字段错误")
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                issues.append(f"character-introductions 第{index + 1}项名称无效")
                continue
            entry_names.append(name.strip())
            introductions_value = entry.get("introductions")
            if not isinstance(introductions_value, list):
                issues.append("character-introductions introductions 必须是数组")
            elif require_empty_introductions and introductions_value:
                issues.append("阶段一的 character-introductions introductions 必须初始化为空数组")
        if set(entry_names) != catalog["characters"] or len(entry_names) != len(set(entry_names)):
            issues.append("character-introductions 角色集合必须与正式角色完全一致且不重复")
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        issues = validate_basis(args.cache_root, require_empty_introductions=True)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues = [str(error)]
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: stage one run basis, assets, introductions, and user intent verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
