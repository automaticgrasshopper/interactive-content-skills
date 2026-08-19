#!/usr/bin/env python3
"""Require a discarded first topology and a structurally different final topology."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import deque
from pathlib import Path

sys.dont_write_bytecode = True

from validate_topology import parse


def node_kind(node: dict[str, object]) -> str:
    interaction = str(node["interaction"])
    if bool(node["ending"]):
        if "小结局" in interaction:
            return "small-ending"
        if "主结局" in interaction:
            return "main-ending"
        if "期望结局" in interaction:
            return "expected-ending"
        if "失败结局" in interaction:
            return "failure-ending"
        return "unclassified-ending"
    if "选择" in interaction and "结果" not in interaction:
        return "choice"
    return "story"


def basic_graph_issues(nodes: dict[str, dict[str, object]], label: str) -> list[str]:
    issues: list[str] = []
    incoming = {node_id: 0 for node_id in nodes}
    for node_id, node in nodes.items():
        successors = list(node["successors"])
        if bool(node["ending"]) != (not successors):
            issues.append(f"{label}的结局与后继状态不一致：{node_id}")
        for target in successors:
            if target not in nodes:
                issues.append(f"{label}的跳转目标不存在：{node_id}->{target}")
            else:
                incoming[target] += 1
    roots = sorted(node_id for node_id, value in incoming.items() if value == 0)
    if roots != ["episode-001"]:
        issues.append(f"{label}入口不唯一或错误：{roots}")
        return issues
    reached: set[str] = set()
    queue = deque(roots)
    while queue:
        node_id = queue.popleft()
        if node_id in reached:
            continue
        reached.add(node_id)
        queue.extend(target for target in nodes[node_id]["successors"] if target in nodes)
    if reached != set(nodes):
        issues.append(f"{label}存在不可达节点")
    indegree = incoming.copy()
    queue = deque(node_id for node_id, value in indegree.items() if value == 0)
    count = 0
    while queue:
        node_id = queue.popleft()
        count += 1
        for target in nodes[node_id]["successors"]:
            if target not in indegree:
                continue
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if count != len(nodes):
        issues.append(f"{label}存在循环")
    return issues


def shape_payload(nodes: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """Canonicalize by rooted option-ordered BFS so renumbering cannot fake a revision."""
    order: list[str] = []
    queued = {"episode-001"}
    queue = deque(["episode-001"])
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in nodes[node_id]["successors"]:
            if target not in queued:
                queued.add(target)
                queue.append(target)
    canonical = {node_id: index for index, node_id in enumerate(order)}
    return [
        {
            "kind": node_kind(nodes[node_id]),
            "successors": [canonical[target] for target in nodes[node_id]["successors"]],
        }
        for node_id in order
    ]


def shape_sha256(nodes: dict[str, dict[str, object]]) -> str:
    payload = json.dumps(shape_payload(nodes), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_revision(first_path: Path, final_path: Path) -> list[str]:
    try:
        first = parse(first_path)
        final = parse(final_path)
    except (OSError, ValueError) as error:
        return [str(error)]
    issues = basic_graph_issues(first, "第一版拓扑")
    issues.extend(basic_graph_issues(final, "第二版拓扑"))
    if not issues and shape_sha256(first) == shape_sha256(final):
        issues.append("第二版拓扑与必须丢弃的第一版形状相同")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("final", type=Path)
    args = parser.parse_args()
    issues = validate_revision(args.first, args.final)
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: 第一版已丢弃；第二版拓扑形状不同且是唯一正式版")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
