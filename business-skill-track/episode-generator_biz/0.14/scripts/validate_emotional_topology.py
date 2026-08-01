#!/usr/bin/env python3
"""Validate an emotional spine and the frozen topology derived from it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from validate_topology import parse, validate


SPINE_VERSION = "nextplay.emotional-spine.v1"
HASH_LINE = re.compile(
    r"^<!--\s*情绪脊校验：\s*(?:sha256:)?([a-f0-9]{64})\s*-->\s*$",
    re.MULTILINE,
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate_spine(spine: Any, node_ids: list[str]) -> list[str]:
    issues: list[str] = []
    if not isinstance(spine, dict):
        return ["情绪脊根对象无效"]
    if spine.get("contract_version") != SPINE_VERSION:
        issues.append(f"情绪脊合同错误：期望 {SPINE_VERSION}")
    entries = spine.get("nodes")
    if not isinstance(entries, list):
        return issues + ["情绪脊 nodes 必须为数组"]
    actual_ids: list[str] = []
    turns = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"情绪脊节点 {index} 不是对象")
            continue
        episode_id = entry.get("episode_id")
        if not isinstance(episode_id, str):
            issues.append(f"情绪脊节点 {index} 缺 episode_id")
            continue
        actual_ids.append(episode_id)
        for field in ("valence", "arousal", "dominance"):
            value = entry.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not -1 <= value <= 1:
                issues.append(f"{episode_id}/{field} 必须是 -1 到 1 的数值")
        turn = entry.get("turn")
        if not isinstance(turn, bool):
            issues.append(f"{episode_id}/turn 必须是布尔值")
        elif turn:
            turns += 1
            if not isinstance(entry.get("turn_reason"), str) or not entry["turn_reason"].strip():
                issues.append(f"{episode_id}/turn_reason 在情绪拐点时必填")
    if actual_ids != node_ids:
        issues.append(f"情绪脊节点顺序与拓扑不一致：{actual_ids}")
    if len(node_ids) > 1 and turns == 0:
        issues.append("情绪脊没有任何真实拐点")
    return issues


def validate_emotional_topology(
    topology_path: Path,
    spine_path: Path,
    structure: Path | None,
    expected_endings: int,
    expected_formal: int | None,
    expected_failure: int | None,
) -> list[str]:
    nodes = parse(topology_path)
    issues = validate(nodes, structure, expected_endings, expected_formal, expected_failure)
    spine = json.loads(spine_path.read_text(encoding="utf-8"))
    issues.extend(validate_spine(spine, list(nodes)))
    digest = hashlib.sha256(canonical_bytes(spine)).hexdigest()
    match = HASH_LINE.search(topology_path.read_text(encoding="utf-8"))
    if not match:
        issues.append("拓扑缺少情绪脊校验哈希")
    elif match.group(1) != digest:
        issues.append(f"拓扑情绪脊校验哈希不一致：期望 {digest}")
    choice_nodes = {node_id for node_id, node in nodes.items() if node["choices"]}
    if isinstance(spine, dict) and isinstance(spine.get("nodes"), list):
        turn_by_id = {item.get("episode_id"): item.get("turn") for item in spine["nodes"] if isinstance(item, dict)}
        for node_id in sorted(choice_nodes):
            if turn_by_id.get(node_id) is not True:
                issues.append(f"选择节点没有对应情绪拐点：{node_id}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("--spine", type=Path, required=True)
    parser.add_argument("--structure", type=Path)
    parser.add_argument("--expected-endings", type=int, required=True)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    args = parser.parse_args()
    try:
        issues = validate_emotional_topology(
            args.topology,
            args.spine,
            args.structure,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    count = len(parse(args.topology))
    print(f"PASS: {count} nodes; emotional spine bound; expected endings verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
