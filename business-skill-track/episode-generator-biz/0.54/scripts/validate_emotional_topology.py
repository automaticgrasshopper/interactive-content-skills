#!/usr/bin/env python3
"""Fail closed unless every frozen route is causally bound to a real emotional spine."""

from __future__ import annotations

from execution_result import not_accepted

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from validate_mainline_emotional_movement import read_movement
from validate_topology import parse, validate


SPINE_VERSION = "nextplay.emotional-spine.v3"
POINT_FIELDS = ("valence", "arousal", "dominance")
ENTRY_FIELDS = {
    "episode_id", "movement_ids", "source_proof", "valence", "arousal",
    "dominance", "turn", "turn_reason", "turn_proof", "unresolved_task",
    "settlement",
}
SETTLEMENTS = {"open", "partial", "resolved"}
MIN_EDGE_SHIFT = 0.05
MIN_TURN_SHIFT = 0.25
MIN_BRANCH_DIVERGENCE = 0.20
HASH_LINE = re.compile(
    r"^<!--\s*情绪脊校验：\s*(?:sha256:)?([a-f0-9]{64})\s*-->\s*$",
    re.MULTILINE,
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def point(entry: dict[str, Any]) -> tuple[float, float, float]:
    return tuple(float(entry[field]) for field in POINT_FIELDS)


def distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return max(abs(left[index] - right[index]) for index in range(3))


def validate_spine(spine: Any, node_ids: list[str]) -> list[str]:
    issues: list[str] = []
    if not isinstance(spine, dict) or set(spine) != {"contract_version", "nodes"}:
        return ["情绪脊根对象必须严格包含contract_version与nodes"]
    if spine.get("contract_version") != SPINE_VERSION:
        issues.append(f"情绪脊合同错误：期望 {SPINE_VERSION}")
    entries = spine.get("nodes")
    if not isinstance(entries, list):
        return issues + ["情绪脊 nodes 必须为数组"]
    actual_ids: list[str] = []
    turns = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != ENTRY_FIELDS:
            issues.append(f"情绪脊节点 {index} 字段错误")
            continue
        episode_id = entry.get("episode_id")
        if not isinstance(episode_id, str):
            issues.append(f"情绪脊节点 {index} 缺 episode_id")
            continue
        actual_ids.append(episode_id)
        movement_ids = entry.get("movement_ids")
        if not isinstance(movement_ids, list) or not movement_ids or any(
            not isinstance(item, str) or not item for item in movement_ids
        ) or len(movement_ids) != len(set(movement_ids)):
            issues.append(f"{episode_id}/movement_ids必须是非空不重复字符串数组")
        for field in POINT_FIELDS:
            value = entry.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not -1 <= value <= 1:
                issues.append(f"{episode_id}/{field} 必须是 -1 到 1 的数值")
        if len(str(entry.get("source_proof") or "").strip()) < 10:
            issues.append(f"{episode_id}/source_proof缺少当前剧情逐字证据")
        if len(str(entry.get("unresolved_task") or "").strip()) < 3:
            issues.append(f"{episode_id}/unresolved_task缺少未结或已结任务")
        if entry.get("settlement") not in SETTLEMENTS:
            issues.append(f"{episode_id}/settlement非法")
        turn = entry.get("turn")
        reason = str(entry.get("turn_reason") or "").strip()
        proof = str(entry.get("turn_proof") or "").strip()
        if not isinstance(turn, bool):
            issues.append(f"{episode_id}/turn 必须是布尔值")
        elif turn:
            turns += 1
            if len(reason) < 8 or len(proof) < 10:
                issues.append(f"{episode_id}真实拐点必须同时提供判断理由和剧情逐字证据")
        elif reason or proof:
            issues.append(f"{episode_id}非拐点不得伪造turn_reason或turn_proof")
    if actual_ids != node_ids:
        issues.append(f"情绪脊节点顺序与拓扑不一致：{actual_ids}")
    if len(node_ids) > 1 and turns == 0:
        issues.append("情绪脊没有任何真实拐点")
    return issues


def read_synopses(cache_root: Path, node_ids: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for node_id in node_ids:
        path = cache_root / "episode-synopses" / f"{node_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("episode_id") != node_id or not isinstance(data.get("synopsis"), str):
            raise ValueError(f"情绪脊无法读取当前冻结梗概：{node_id}")
        result[node_id] = data["synopsis"]
    return result


def all_paths(nodes: dict[str, dict[str, object]]) -> list[list[str]]:
    paths: list[list[str]] = []

    def walk(node_id: str, route: list[str]) -> None:
        successors = list(nodes[node_id]["successors"])
        current = [*route, node_id]
        if not successors:
            paths.append(current)
            return
        for target in successors:
            walk(target, current)

    walk("episode-001", [])
    return paths


def validate_emotional_topology(
    cache_root: Path,
    topology_path: Path,
    spine_path: Path,
    expected_major: int,
    expected_main: int | None,
    expected_desired: int | None,
    expected_failure: int | None,
    expected_small: int | None,
) -> list[str]:
    nodes = parse(topology_path)
    issues = validate(nodes, expected_major, expected_main, expected_desired, expected_failure, expected_small)
    spine = json.loads(spine_path.read_text(encoding="utf-8"))
    node_ids = list(nodes)
    issues.extend(validate_spine(spine, node_ids))
    if issues:
        return list(dict.fromkeys(issues))

    _, movement = read_movement(cache_root)
    valid_movements = {str(item["movement_id"]) for item in movement["movements"]}
    synopses = read_synopses(cache_root, node_ids)
    entries = {str(item["episode_id"]): item for item in spine["nodes"]}
    points = {node_id: point(entries[node_id]) for node_id in node_ids}

    for node_id, entry in entries.items():
        invalid_movements = sorted(set(entry["movement_ids"]) - valid_movements)
        if invalid_movements:
            issues.append(f"{node_id}引用不存在的拓扑前情绪运动：{invalid_movements}")
        proof = str(entry["source_proof"]).strip()
        if proof not in synopses[node_id]:
            issues.append(f"{node_id}情绪状态证据不在当前冻结梗概")
        turn_proof = str(entry["turn_proof"]).strip()
        if entry["turn"] is True and turn_proof not in synopses[node_id]:
            issues.append(f"{node_id}拐点证据不在当前冻结梗概")
        ending = bool(nodes[node_id]["ending"])
        if ending and entry["settlement"] != "resolved":
            issues.append(f"结局没有完成情绪结算：{node_id}")
        if not ending and entry["settlement"] == "resolved":
            issues.append(f"非结局提前宣称情绪任务全部结算：{node_id}")

    incoming: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for source, node in nodes.items():
        for target in node["successors"]:
            incoming[target].append(source)
            shift = distance(points[source], points[target])
            if shift < MIN_EDGE_SHIFT:
                issues.append(f"相邻节点没有可验证的情绪或控制权位移：{source}->{target}")
            if shift >= MIN_TURN_SHIFT and entries[target]["turn"] is not True:
                issues.append(f"显著情绪位移没有标记真实拐点：{source}->{target}")

    for node_id, node in nodes.items():
        successors = list(node["successors"])
        if not node["choices"]:
            continue
        if len(successors) < 2:
            continue
        divergence = max(
            distance(points[left], points[right])
            for offset, left in enumerate(successors)
            for right in successors[offset + 1:]
        )
        if divergence < MIN_BRANCH_DIVERGENCE:
            issues.append(f"选择后的路线没有形成不同情绪方向：{node_id}")
        if entries[node_id]["turn"] is not True and divergence < MIN_TURN_SHIFT:
            issues.append(f"选择既不是当前拐点，也没有造成足够强的后续方向分歧：{node_id}")

    routes = all_paths(nodes)
    for route in routes:
        shifts = [distance(points[left], points[right]) for left, right in zip(route, route[1:])]
        if len(route) > 1 and max(shifts, default=0) < MIN_TURN_SHIFT:
            issues.append(f"完整路线没有真实情绪拐点：{'->'.join(route)}")
        if entries[route[-1]]["settlement"] != "resolved":
            issues.append(f"完整路线抵达结局时仍未结算：{'->'.join(route)}")

    major = [
        node_id for node_id, node in nodes.items()
        if node["ending"] and any(kind in str(node["interaction"]) for kind in ("主结局", "期望结局", "失败结局"))
    ]
    for offset, left in enumerate(major):
        for right in major[offset + 1:]:
            if distance(points[left], points[right]) < 0.15:
                issues.append(f"主要结局没有形成不同情绪落点：{left}/{right}")

    digest = hashlib.sha256(canonical_bytes(spine)).hexdigest()
    match = HASH_LINE.search(topology_path.read_text(encoding="utf-8"))
    if not match:
        issues.append("拓扑缺少情绪脊校验哈希")
    elif match.group(1) != digest:
        issues.append(f"拓扑情绪脊校验哈希不一致：期望 {digest}")
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        from planning_acceptance import resolved_endings

        endings = resolved_endings(args.cache_root)
        issues = validate_emotional_topology(
            args.cache_root,
            args.cache_root / "topology.md",
            args.cache_root / "emotional-spine.json",
            endings["major"], endings["main"], endings["expected"],
            endings["failure"], endings["small"],
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return not_accepted(__file__)
    print("PASS: every route is causally bound to a distinct, evidence-backed emotional spine")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli

    raise SystemExit(run_cli(main, __file__))
