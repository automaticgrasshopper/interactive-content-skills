#!/usr/bin/env python3
"""Validate the allowlisted creative brief and its user-intent binding."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import json
from pathlib import Path
from typing import Any

from validate_user_intent_lock import validate_contract


CONTRACT_VERSION = "nextplay.episode-creative-brief.v1"
ROOT_FIELDS = {
    "contract_version", "user_intent_contract_sha256", "title", "logline",
    "story_description", "story_volume", "assets", "user_constraints",
}
ASSET_TYPES = ("characters", "scenes", "props")
FORBIDDEN_KEYS = {
    "node_count_hint", "node_count_suggestion", "episode_count", "episode_count_hint",
    "theme", "key_events", "required_events", "world_rules", "ending_plan",
    "emotional_spine", "structure_type", "interaction_count",
}


def walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(walk_keys(item))
    return keys


def validate_value(value: Any, contract: dict[str, Any], contract_sha: str) -> list[str]:
    issues: list[str] = []
    if not isinstance(value, dict) or set(value) != ROOT_FIELDS:
        return ["creative-brief.json 根字段错误"]
    if value.get("contract_version") != CONTRACT_VERSION:
        issues.append(f"创作简报合同错误：期望 {CONTRACT_VERSION}")
    if value.get("user_intent_contract_sha256") != contract_sha:
        issues.append("创作简报未绑定当前用户意图合同")
    if not isinstance(value.get("title"), str) or not value["title"].strip():
        issues.append("创作简报缺少标题")
    for field in ("logline", "story_volume"):
        item = value.get(field)
        if item is not None and (not isinstance(item, str) or not item.strip()):
            issues.append(f"{field} 必须是非空字符串或 null")
    if not isinstance(value.get("story_description"), str) or not value["story_description"].strip():
        issues.append("创作简报缺少用户端展示的大纲正文")
    assets = value.get("assets")
    if not isinstance(assets, dict) or set(assets) != set(ASSET_TYPES):
        issues.append("创作简报 assets 字段错误")
        assets = {}
    for kind in ASSET_TYPES:
        items = assets.get(kind)
        if not isinstance(items, list):
            issues.append(f"assets.{kind} 必须是数组")
            continue
        names: set[str] = set()
        for index, item in enumerate(items, 1):
            if not isinstance(item, dict) or set(item) != {"name", "description"}:
                issues.append(f"assets.{kind} 第{index}项只能包含 name 与 description")
                continue
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            if not name or not description or name in names:
                issues.append(f"assets.{kind} 第{index}项名称、描述为空或名称重复")
            names.add(name)
    expected_constraints = [
        item for item in contract.get("constraints", [])
        if isinstance(item, dict) and item.get("required") is True
    ]
    if value.get("user_constraints") != expected_constraints:
        issues.append("创作简报必须逐项复制全部当前用户硬约束，不得增删改")
    forbidden = sorted(walk_keys(value) & FORBIDDEN_KEYS)
    if forbidden:
        issues.append(f"创作简报含禁用上游字段：{forbidden}")
    return list(dict.fromkeys(issues))


def validate_frozen(cache_root: Path) -> dict[str, Any]:
    contract, contract_sha, intent_issues = validate_contract(cache_root)
    if intent_issues:
        raise ValueError("；".join(intent_issues))
    path = cache_root / "creative-brief.json"
    if not path.is_file():
        raise ValueError("缺少 creative-brief.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    issues = validate_value(value, contract, contract_sha)
    if issues:
        raise ValueError("；".join(issues))
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        validate_frozen(args.cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    print("PASS: creative brief contains only visible story, volume, assets, and user locks")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
