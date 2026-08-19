#!/usr/bin/env python3
"""Validate one episode immediately before its semantic quality review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from episode_artifact import predecessors, validate_episode
from validate_character_appearances import (
    INTRODUCTION_FIELDS,
    asset_values,
    first_appearance_nodes,
    load_asset_catalog,
    load_character_facts,
    load_introduction_audit,
    mentioned_characters,
    section,
    subsection,
    validate_introduction_facts,
)
from validate_topology import parse


def registry_style_introductions(script: str, characters: set[str]) -> list[str]:
    """Find repeated first mentions written as character-card declarations."""
    hits: list[str] = []
    for character in sorted(characters):
        location = script.find(character)
        if location < 0:
            continue
        tail = script[location:location + 48]
        if re.match(rf"{re.escape(character)}\s*(?:是|为|担任)", tail):
            hits.append(character)
    return hits


def role_card_dialogue(script: str, character_facts: dict[str, dict[str, object]]) -> list[str]:
    """Reject full frozen job titles restated with a copula in dialogue."""
    hits: list[str] = []
    for line in script.splitlines():
        if "：" not in line:
            continue
        speaker, dialogue = line.split("：", 1)
        compact = re.sub(r"[\s\W_]+", "", dialogue, flags=re.UNICODE)
        for character, facts in character_facts.items():
            identity = re.sub(r"[\s\W_]+", "", str(facts.get("identity") or ""), flags=re.UNICODE)
            identity = identity.replace(character, "")
            identity = re.sub(r"^(?:是|为|作为|担任|系)", "", identity)
            if identity and identity in compact and re.search(
                rf"(?:我|你|他|她|{re.escape(character)})?(?:是|为|担任){re.escape(identity)}",
                compact,
            ):
                hits.append(f"{speaker.strip()}：{dialogue.strip()}")
    return hits


def validate_one(cache_root: Path, episode_id: str) -> list[str]:
    topology_path = cache_root / "topology.md"
    nodes = parse(topology_path)
    if episode_id not in nodes:
        return [f"冻结拓扑不存在分集：{episode_id}"]
    path = cache_root / "episodes" / f"{episode_id}.md"
    if not path.is_file():
        return [f"缺少分集正文：{episode_id}"]
    catalog = load_asset_catalog(cache_root / "asset-catalog.json")
    text = path.read_text(encoding="utf-8").strip()
    issues, _ = validate_episode(
        episode_id,
        nodes[episode_id],
        text,
        catalog,
        predecessors(nodes)[episode_id],
    )
    try:
        full_script = subsection(section(text, "分集剧本"), "完整剧本")
        listed = asset_values(section(text, "关联角色"))
    except ValueError as error:
        return list(dict.fromkeys([*issues, f"{episode_id}/{error}"]))
    enhanced_path = cache_root / "enhanced-screenplays" / f"{episode_id}.md"
    if not enhanced_path.is_file():
        issues.append(f"缺少Enhancer增强稿：{episode_id}")
    elif enhanced_path.read_text(encoding="utf-8").strip() != full_script:
        issues.append(f"正式正文不是Enhancer增强稿的逐字副本：{episode_id}")
    unknown = listed - catalog["characters"]
    if unknown:
        issues.append(f"出现非正式角色资产：{episode_id}={sorted(unknown)}")
    listed_formal = listed & catalog["characters"]
    mentioned = mentioned_characters(full_script, catalog)
    character_facts = load_character_facts(cache_root / "creative-brief.json")
    registry_hits = registry_style_introductions(full_script, catalog["characters"])
    if len(registry_hits) >= 2:
        issues.append(
            f"多名角色首次出现采用人物登记句：{episode_id}={registry_hits}；"
            "请把身份与关系放回动作、称呼、反应或自然对白"
        )
    dialogue_role_hits = role_card_dialogue(full_script, character_facts)
    if dialogue_role_hits:
        issues.append(
            f"对白直接复述冻结职位卡：{episode_id}={dialogue_role_hits}；"
            "请把职位放进出场动作或自然称谓"
        )
    if listed_formal - mentioned:
        issues.append(f"关联角色未在正文出现：{episode_id}={sorted(listed_formal - mentioned)}")
    if mentioned - listed_formal:
        issues.append(f"正文正式角色未登记：{episode_id}={sorted(mentioned - listed_formal)}")

    episode_characters: dict[str, set[str]] = {}
    for node_id in nodes:
        episode_path = cache_root / "episodes" / f"{node_id}.md"
        if not episode_path.is_file():
            episode_characters[node_id] = set()
            continue
        try:
            artifact = episode_path.read_text(encoding="utf-8").strip()
            episode_script = subsection(section(artifact, "分集剧本"), "完整剧本")
            episode_characters[node_id] = mentioned_characters(episode_script, catalog)
        except (OSError, ValueError):
            episode_characters[node_id] = set()
    audit = load_introduction_audit(
        cache_root / "character-introductions.json",
        catalog,
    )
    for character in sorted(listed_formal):
        if episode_id not in first_appearance_nodes(nodes, episode_characters, character):
            continue
        entries = (audit.get(character) or {}).get("introductions")
        current_entries = [
            item
            for item in entries or []
            if isinstance(item, dict) and item.get("episode_id") == episode_id
        ]
        if len(current_entries) != 1:
            issues.append(f"当前路径首次出场缺少唯一审计：{character}/{episode_id}")
            continue
        entry = current_entries[0]
        for field in INTRODUCTION_FIELDS:
            evidence = entry.get(field)
            if not isinstance(evidence, str) or len(evidence.strip()) < 6:
                issues.append(f"当前路径首次出场证据不完整：{character}/{episode_id}/{field}")
            elif evidence not in full_script:
                issues.append(f"当前路径首次出场证据不在正文：{character}/{episode_id}/{field}")
        issues.extend(validate_introduction_facts(character, episode_id, entry, character_facts))
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("episode_id")
    args = parser.parse_args()
    try:
        issues = validate_one(args.cache_root, args.episode_id)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues = [str(error)]
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        f"PASS: {args.episode_id} structure, topology, assets, opening, "
        "and path-aware introductions verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
