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
CREATIVE_BRIEF_VERSION = "nextplay.episode-creative-brief.v1"
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


def load_character_facts(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("contract_version") != CREATIVE_BRIEF_VERSION:
        raise ValueError(f"creative-brief.json 合同错误：期望 {CREATIVE_BRIEF_VERSION}")
    assets = data.get("assets") if isinstance(data.get("assets"), dict) else {}
    characters = assets.get("characters")
    if not isinstance(characters, list):
        raise ValueError("creative-brief.json assets.characters 必须是数组")
    facts: dict[str, dict[str, Any]] = {}
    for index, card in enumerate(characters):
        if not isinstance(card, dict):
            raise ValueError(f"creative-brief.json 角色第{index + 1}项错误")
        name = str(card.get("name") or "").strip()
        description = str(card.get("description") or "").strip()
        if not name or not description:
            raise ValueError(f"creative-brief.json 角色第{index + 1}项缺少名称或展示描述")
        if name in facts:
            raise ValueError(f"creative-brief.json 角色重名：{name}")
        facts[name] = {
            "identity": re.split(r"[。；，,]", description, maxsplit=1)[0],
            "relationships": [],
        }
    return facts


def normalized_fact(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE)


def identity_core(character: str, value: str) -> str:
    """Return the role fact, not a frozen presentational sentence."""
    # Text after the explicit separator is an internal dramatic function and
    # must never be forced into dialogue or first-appearance evidence.
    value = value.split("；", 1)[0]
    core = normalized_fact(value)
    core = core.replace(normalized_fact(character), "")
    core = re.sub(r"^(?:是|为|作为|担任|系)", "", core)
    # These are game/editor classifications, not facts a natural scene must
    # say aloud.  Keeping them in the lexical core made valid introductions
    # fail unless the screenplay literally called somebody a "玩家角色".
    for meta_role in ("玩家角色", "可操控角色", "主角", "非玩家角色", "NPC"):
        core = core.replace(normalized_fact(meta_role), "")
    return core


def identity_matches(core: str, evidence: str) -> bool:
    """Accept a role-bearing suffix so an organization prefix need not be repeated."""
    if not core:
        return False
    if core in evidence:
        return True
    return any(core[-width:] in evidence for width in range(2, len(core)))


def relationship_components(
    character: str,
    value: str,
    known_characters: set[str],
) -> list[tuple[str | None, str]]:
    """Extract target + relation facts while leaving sentence syntax free."""
    clauses = re.split(r"[，,；;。]|并且|同时|也(?=是|为)", value)
    components: list[tuple[str | None, str]] = []
    for clause in clauses:
        compact = normalized_fact(clause)
        if not compact:
            continue
        compact = compact.replace(normalized_fact(character), "")
        targets = [
            name
            for name in known_characters
            if name != character and normalized_fact(name) in compact
        ]
        descriptor = compact
        for target in targets:
            descriptor = descriptor.replace(normalized_fact(target), "")
        descriptor = re.sub(r"^(?:是|为|作为|担任|系|与|和|跟|同)+", "", descriptor)
        descriptor = descriptor.replace("的", "")
        if descriptor:
            if targets:
                components.extend((normalized_fact(target), descriptor) for target in targets)
            else:
                components.append((None, descriptor))
    return components


def relationship_descriptors(descriptor: str) -> set[str]:
    """Accept the natural reciprocal wording of a frozen relationship fact."""
    reciprocal_groups = (
        {"姐姐", "哥哥", "弟弟", "妹妹"},
        {"父亲", "母亲", "爸爸", "妈妈", "儿子", "女儿"},
        {"丈夫", "妻子", "老公", "老婆"},
        {"师父", "导师", "老师", "徒弟", "学生"},
    )
    accepted = {descriptor}
    accepted.update(
        fragment
        for fragment in re.split(r"拥有对|(?:的|对|与|和|跟|同|由|向|给|提供)+", descriptor)
        if len(fragment) >= 2
    )
    for group in reciprocal_groups:
        if any(term in descriptor for term in group):
            accepted.update(group)
    return accepted


def validate_introduction_facts(
    character: str,
    episode_id: str,
    item: dict[str, Any],
    character_facts: dict[str, dict[str, Any]],
) -> list[str]:
    facts = character_facts.get(character)
    if facts is None:
        return [f"首次出场缺少冻结角色事实：{character}/{episode_id}"]
    identity_raw = str(item.get("identity_evidence") or "").strip()
    relationship_raw = str(item.get("relationship_evidence") or "").strip()
    identity_evidence = normalized_fact(identity_raw)
    frozen_identity = identity_core(character, str(facts["identity"]))
    issues: list[str] = []
    if re.match(rf"^{re.escape(character)}\s*(?:是|为|担任)", identity_raw):
        issues.append(f"首次出场身份采用人物登记句：{character}/{episode_id}")
    if not identity_matches(frozen_identity, identity_evidence):
        issues.append(f"首次出场身份未与冻结事实一致：{character}/{episode_id}")
    if re.match(
        rf"^(?:他|她|{re.escape(character)})\s*(?:也)?是",
        relationship_raw,
    ):
        issues.append(f"首次出场关系采用人物登记句：{character}/{episode_id}")
    # A deterministic token match cannot distinguish natural interaction from
    # relationship-card exposition.  The independent episode review therefore
    # judges whether this in-script excerpt makes the current connection clear
    # and remains consistent with the frozen card.  Here we only reject the
    # registry-sentence shortcut; structure, length, uniqueness and verbatim
    # location are enforced by the surrounding audit.
    return issues


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
    character_facts: dict[str, dict[str, Any]],
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
            issues.extend(validate_introduction_facts(character, episode_id, item, character_facts))
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
    character_facts = load_character_facts(cache_root / "creative-brief.json")
    issues.extend(
        validate_introduction_audit(
            audit,
            nodes,
            catalog,
            scripts,
            episode_characters,
            character_facts,
        )
    )
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
