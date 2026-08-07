#!/usr/bin/env python3
"""Validate formal-character coverage, declarations, and path-aware introductions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from validate_topology import parse


ASSET_VERSION = "nextplay.episode-assets.v1"
INTRODUCTION_VERSION = "nextplay.character-introductions.v1"
INTRODUCTION_FIELDS = (
    "identity_evidence",
    "relationship_evidence",
    "immediate_relevance_evidence",
)


def section(text: str, name: str) -> str:
    match = re.search(rf"^# {re.escape(name)}\s*\n+(.*?)(?=^# |\Z)", text, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"缺少一级字段：{name}")
    return match.group(1).strip()


def subsection(block: str, name: str) -> str:
    match = re.search(rf"^## {re.escape(name)}\s*\n+(.*?)(?=^## |\Z)", block, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"缺少二级字段：{name}")
    return match.group(1).strip()


def asset_values(block: str) -> set[str]:
    values: set[str] = set()
    for raw in re.split(r"[、，,\n]", block):
        value = re.sub(r"^\s*[-*]\s*", "", raw).strip().strip("`")
        if value and value != "无":
            values.add(value)
    return values


def string_array(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} 必须是非空字符串数组")
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field} 存在重名")
    return normalized


def load_asset_catalog(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("contract_version") != ASSET_VERSION:
        raise ValueError(f"asset-catalog.json 合同错误：期望 {ASSET_VERSION}")
    result: dict[str, Any] = {}
    for key in ("characters", "scenes", "props"):
        result[key] = set(string_array(data.get(key), f"asset catalog {key}"))

    optional = set(string_array(data.get("optional_characters", []), "asset catalog optional_characters"))
    if not optional <= result["characters"]:
        raise ValueError("asset catalog optional_characters 含非正式角色")
    result["optional_characters"] = optional

    aliases = data.get("character_aliases", {})
    if not isinstance(aliases, dict) or any(key not in result["characters"] for key in aliases):
        raise ValueError("asset catalog character_aliases 必须只使用正式角色名")
    alias_to_character: dict[str, str] = {}
    aliases_by_character: dict[str, set[str]] = {}
    for character in result["characters"]:
        character_aliases = {
            character,
            *string_array(aliases.get(character, []), f"asset catalog {character} 的别名"),
        }
        for alias in character_aliases:
            owner = alias_to_character.get(alias)
            if owner is not None and owner != character:
                raise ValueError(f"角色别名冲突：{alias} 同时属于 {owner}、{character}")
            alias_to_character[alias] = character
        aliases_by_character[character] = character_aliases
    result["alias_to_character"] = alias_to_character
    result["aliases_by_character"] = aliases_by_character
    return result


def mentioned_characters(text: str, catalog: dict[str, Any]) -> set[str]:
    return {
        character
        for alias, character in catalog["alias_to_character"].items()
        if alias in text
    }


def topological_order(nodes: dict[str, dict[str, object]]) -> list[str]:
    incoming = {node_id: 0 for node_id in nodes}
    for node in nodes.values():
        for target in node["successors"]:
            if target in incoming:
                incoming[target] += 1
    queue = sorted(node_id for node_id, degree in incoming.items() if degree == 0)
    order: list[str] = []
    while queue:
        node_id = queue.pop(0)
        order.append(node_id)
        for target in nodes[node_id]["successors"]:
            if target not in incoming:
                continue
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
                queue.sort()
    return order


def first_appearance_nodes(
    nodes: dict[str, dict[str, object]],
    episode_characters: dict[str, set[str]],
    character: str,
) -> list[str]:
    order = topological_order(nodes)
    if not order:
        return []
    unseen_before = {node_id: False for node_id in nodes}
    unseen_before[order[0]] = True
    introductions: list[str] = []
    for node_id in order:
        unseen_here = unseen_before[node_id]
        appears_here = character in episode_characters.get(node_id, set())
        if unseen_here and appears_here:
            introductions.append(node_id)
        if unseen_here and not appears_here:
            for target in nodes[node_id]["successors"]:
                if target in unseen_before:
                    unseen_before[target] = True
    return introductions


def read_episode_character_state(
    cache_root: Path,
    nodes: dict[str, dict[str, object]],
    catalog: dict[str, Any],
) -> tuple[list[str], dict[str, str], dict[str, set[str]]]:
    issues: list[str] = []
    scripts: dict[str, str] = {}
    episode_characters: dict[str, set[str]] = {}
    for node_id in nodes:
        path = cache_root / "episodes" / f"{node_id}.md"
        if not path.is_file():
            issues.append(f"角色门禁缺少正文：{node_id}")
            continue
        artifact = path.read_text(encoding="utf-8").strip()
        try:
            full_script = subsection(section(artifact, "分集剧本"), "完整剧本")
            listed = asset_values(section(artifact, "关联角色"))
        except ValueError as error:
            issues.append(f"{node_id}/角色门禁/{error}")
            continue
        unknown = listed - catalog["characters"]
        if unknown:
            issues.append(f"出现非正式角色资产：{node_id}={sorted(unknown)}")
        listed_formal = listed & catalog["characters"]
        mentioned = mentioned_characters(full_script, catalog)
        unmentioned = listed_formal - mentioned
        undeclared = mentioned - listed_formal
        if unmentioned:
            issues.append(f"关联角色未在正文出现：{node_id}={sorted(unmentioned)}")
        if undeclared:
            issues.append(f"正文正式角色未登记：{node_id}={sorted(undeclared)}")
        scripts[node_id] = full_script
        episode_characters[node_id] = listed_formal
    return issues, scripts, episode_characters


def load_introduction_audit(path: Path, catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("contract_version") != INTRODUCTION_VERSION:
        raise ValueError(f"character-introductions.json 合同错误：期望 {INTRODUCTION_VERSION}")
    entries = data.get("characters")
    if not isinstance(entries, list):
        raise ValueError("character-introductions.json characters 必须为数组")
    by_name: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"name", "introductions"}:
            raise ValueError(f"character-introductions 角色 {index} 字段错误")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"character-introductions 角色 {index} 名称无效")
        name = name.strip()
        if name in by_name:
            raise ValueError(f"character-introductions 角色重名：{name}")
        if name not in catalog["characters"]:
            raise ValueError(f"character-introductions 含非正式角色：{name}")
        by_name[name] = entry
    return by_name


def validate_introduction_audit(
    audit: dict[str, dict[str, Any]],
    nodes: dict[str, dict[str, object]],
    catalog: dict[str, Any],
    scripts: dict[str, str],
    episode_characters: dict[str, set[str]],
) -> list[str]:
    issues: list[str] = []
    used = set().union(*episode_characters.values()) if episode_characters else set()
    required = catalog["characters"] - catalog["optional_characters"]
    missing_required = sorted(required - used)
    if missing_required:
        issues.append(f"正式角色从未出场：{missing_required}")
    missing_audits = sorted(used - set(audit))
    extra_audits = sorted(set(audit) - used)
    if missing_audits:
        issues.append(f"缺少角色首次出场审计：{missing_audits}")
    if extra_audits:
        issues.append(f"未出场角色却有首次出场审计：{extra_audits}")

    for character in sorted(used & set(audit)):
        introductions = audit[character].get("introductions")
        if not isinstance(introductions, list):
            raise ValueError(f"{character}/introductions 必须为数组")
        declared: list[str] = []
        for index, item in enumerate(introductions):
            expected_fields = {"episode_id", *INTRODUCTION_FIELDS}
            if not isinstance(item, dict) or set(item) != expected_fields:
                raise ValueError(f"{character}/introductions/{index} 字段错误")
            episode_id = item.get("episode_id")
            if not isinstance(episode_id, str) or episode_id not in nodes:
                raise ValueError(f"{character}/introductions/{index} 分集编号无效")
            declared.append(episode_id)
            evidence = [item.get(field) for field in INTRODUCTION_FIELDS]
            if any(not isinstance(value, str) or len(value.strip()) < 6 for value in evidence):
                issues.append(f"首次出场证据不完整：{character}/{episode_id}")
                continue
            quotes = [value.strip() for value in evidence]
            if len(set(quotes)) != len(quotes):
                issues.append(f"首次出场三类证据不得重复：{character}/{episode_id}")
            if not any(alias in quotes[0] for alias in catalog["aliases_by_character"][character]):
                issues.append(f"身份交代证据未点明角色：{character}/{episode_id}")
            for field, quote in zip(INTRODUCTION_FIELDS, quotes):
                if quote not in scripts.get(episode_id, ""):
                    issues.append(f"首次出场证据无法在正文定位：{character}/{episode_id}/{field}")
        if len(declared) != len(set(declared)):
            issues.append(f"首次出场分集重复：{character}")
        expected = first_appearance_nodes(nodes, episode_characters, character)
        if declared != expected:
            issues.append(f"首次出场分集与观看路径不一致：{character}={declared} expected={expected}")
    return issues


def validate_character_appearance_project(
    cache_root: Path,
    nodes: dict[str, dict[str, object]],
    catalog: dict[str, Any],
    introduction_path: Path,
) -> list[str]:
    issues, scripts, episode_characters = read_episode_character_state(cache_root, nodes, catalog)
    audit = load_introduction_audit(introduction_path, catalog)
    issues.extend(validate_introduction_audit(audit, nodes, catalog, scripts, episode_characters))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--asset-catalog", type=Path)
    parser.add_argument("--introductions", type=Path)
    args = parser.parse_args()
    try:
        nodes = parse(args.cache_root / "topology.md")
        catalog = load_asset_catalog(args.asset_catalog or args.cache_root / "asset-catalog.json")
        issues = validate_character_appearance_project(
            args.cache_root,
            nodes,
            catalog,
            args.introductions or args.cache_root / "character-introductions.json",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"PASS: {len(nodes)} episodes; character coverage, declarations, and introductions verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
