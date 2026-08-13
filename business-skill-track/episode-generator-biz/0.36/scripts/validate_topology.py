#!/usr/bin/env python3
"""Validate a generic one-node-one-episode topology without project-specific assets."""

from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path


HEADER = re.compile(r"^##\s+(episode-(\d{3}))\s*｜\s*(.+?)\s*$", re.MULTILINE)
EPISODE = re.compile(r"episode-\d{3}")
TOPOLOGY_CONTRACT_VERSION = "nextplay.episode-topology.v1"
TOPOLOGY_CONTRACT = re.compile(
    r"^<!--\s*拓扑合同：\s*(\{.*\})\s*-->\s*$",
    re.MULTILINE,
)


def field(block: str, name: str) -> str:
    match = re.search(rf"^-\s*{re.escape(name)}：\s*(.*?)\s*$", block, re.MULTILINE)
    if not match:
        raise ValueError(f"缺少字段：{name}")
    return match.group(1).strip()


def optional_field(block: str, name: str) -> str:
    match = re.search(rf"^-\s*{re.escape(name)}：\s*(.*?)\s*$", block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse(path: Path) -> dict[str, dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    contract_match = TOPOLOGY_CONTRACT.search(text)
    if not contract_match:
        raise ValueError("缺少拓扑合同")
    try:
        contract = json.loads(contract_match.group(1))
    except json.JSONDecodeError as error:
        raise ValueError(f"拓扑合同不是有效JSON：{error}") from error
    if not isinstance(contract, dict) or set(contract) != {
        "contract_version",
        "resolved_node_count",
        "count_source",
    }:
        raise ValueError("拓扑合同字段错误")
    if contract.get("contract_version") != TOPOLOGY_CONTRACT_VERSION:
        raise ValueError(f"拓扑合同版本错误：期望 {TOPOLOGY_CONTRACT_VERSION}")
    resolved_count = contract.get("resolved_node_count")
    if not isinstance(resolved_count, int) or isinstance(resolved_count, bool) or resolved_count < 1:
        raise ValueError("拓扑合同 resolved_node_count 必须是正整数")
    if contract.get("count_source") != "causal-expansion":
        raise ValueError("拓扑合同 count_source 必须是 causal-expansion")
    matches = list(HEADER.finditer(text))
    if not matches:
        raise ValueError("未找到分集节点")
    nodes: dict[str, dict[str, object]] = {}
    for index, match in enumerate(matches):
        node_id = match.group(1)
        if node_id in nodes:
            raise ValueError(f"重复节点：{node_id}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : end]
        successor_text = field(block, "后续节点")
        successors = EPISODE.findall(successor_text) if successor_text != "无" else []
        choices = re.findall(
            r"^-\s*选择：\s*(.*?)\s*(?:->|→)\s*(episode-\d{3})\s*$",
            block,
            re.MULTILINE,
        )
        nodes[node_id] = {
            "number": int(match.group(2)),
            "title": match.group(3).strip(),
            "successors": successors,
            "choices": choices,
            "question": optional_field(block, "选择问题"),
            "interaction": field(block, "互动类型"),
            "ending": field(block, "结局") == "是",
        }
    if resolved_count != len(nodes):
        raise ValueError(
            f"拓扑合同节点数与实际不一致：合同{resolved_count}，实际{len(nodes)}"
        )
    return nodes


def validate(
    nodes: dict[str, dict[str, object]],
    expected_endings: int | None = None,
    expected_formal: int | None = None,
    expected_failure: int | None = None,
    movement: dict[str, object] | None = None,
) -> list[str]:
    issues: list[str] = []
    expected_numbers = list(range(1, len(nodes) + 1))
    actual_numbers = sorted(int(node["number"]) for node in nodes.values())
    if actual_numbers != expected_numbers:
        issues.append(f"编号不连续：{actual_numbers}")

    incoming = {node_id: 0 for node_id in nodes}
    for node_id, node in nodes.items():
        successors = list(node["successors"])
        if len(successors) != len(set(successors)):
            issues.append(f"重复后继：{node_id}")
        if node_id in successors:
            issues.append(f"节点自环：{node_id}")
        ending = bool(node["ending"])
        if ending and successors:
            issues.append(f"结局仍有后继：{node_id}")
        if not ending and not successors:
            issues.append(f"非结局缺少后继：{node_id}")
        for target in successors:
            if target not in nodes:
                issues.append(f"跳转目标不存在：{node_id}->{target}")
            else:
                incoming[target] += 1

        choices = list(node["choices"])
        is_choice = "选择" in str(node["interaction"]) and "结果" not in str(node["interaction"])
        targets = [target for _, target in choices]
        if is_choice:
            if len(choices) < 2 or len(set(targets)) < 2:
                issues.append(f"选择出口不足两个不同目标：{node_id}")
            if set(targets) != set(successors):
                issues.append(f"选择目标与后继不一致：{node_id}")
        elif choices:
            issues.append(f"非选择节点含选择项：{node_id}")

    roots = sorted(node_id for node_id, count in incoming.items() if count == 0)
    if roots != ["episode-001"]:
        issues.append(f"入口不唯一或错误：{roots}")

    visited: set[str] = set()
    queue = deque(roots)
    while queue:
        node_id = queue.popleft()
        if node_id in visited or node_id not in nodes:
            continue
        visited.add(node_id)
        queue.extend(target for target in nodes[node_id]["successors"] if target in nodes)
    missing = sorted(set(nodes) - visited)
    if missing:
        issues.append(f"存在不可达节点：{missing}")

    indegree = incoming.copy()
    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    count = 0
    topological_order: list[str] = []
    while queue:
        node_id = queue.popleft()
        count += 1
        topological_order.append(node_id)
        for target in nodes[node_id]["successors"]:
            if target not in indegree:
                continue
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if count != len(nodes):
        issues.append("拓扑存在循环")

    gap_by_node: dict[str, int] = {}
    if roots == ["episode-001"] and count == len(nodes):
        for node_id in topological_order:
            interaction = str(nodes[node_id]["interaction"])
            is_choice = "选择" in interaction and "结果" not in interaction
            predecessors = [
                source
                for source, node in nodes.items()
                if node_id in node["successors"]
            ]
            previous_gap = max((gap_by_node.get(source, 0) for source in predecessors), default=0)
            gap_by_node[node_id] = 0 if is_choice else previous_gap + 1
            if gap_by_node[node_id] > 4:
                issues.append(f"连续无互动节点超过四个：{node_id}")

    reverse = {node_id: [] for node_id in nodes}
    ending_nodes = {node_id for node_id, node in nodes.items() if bool(node["ending"])}
    for source, node in nodes.items():
        for target in node["successors"]:
            if target in reverse:
                reverse[target].append(source)
    can_reach_ending = set(ending_nodes)
    queue = deque(ending_nodes)
    while queue:
        target = queue.popleft()
        for source in reverse[target]:
            if source not in can_reach_ending:
                can_reach_ending.add(source)
                queue.append(source)
    no_ending_path = sorted(set(nodes) - can_reach_ending)
    if no_ending_path:
        issues.append(f"存在无法到达结局的节点：{no_ending_path}")

    total_endings = len(ending_nodes)
    minor = sum(1 for node in nodes.values() if node["ending"] and "独立小结局" in str(node["interaction"]))
    formal = sum(1 for node in nodes.values() if node["ending"] and "主要正式结局" in str(node["interaction"]))
    failure = sum(1 for node in nodes.values() if node["ending"] and "主要失败结局" in str(node["interaction"]))
    if total_endings == 0:
        issues.append("没有可达结局")
    if expected_endings is not None and expected_endings < 1:
        issues.append("期望结局数必须大于 0")
    elif expected_endings is not None and total_endings - minor != expected_endings:
        issues.append(f"主要结局数量错误：期望{expected_endings}，实际{total_endings - minor}；独立小结局{minor}不计入预算")
    if expected_formal is not None and formal != expected_formal:
        issues.append(f"正式结局数量错误：期望{expected_formal}，实际{formal}")
    if expected_failure is not None and failure != expected_failure:
        issues.append(f"失败小结局数量错误：期望{expected_failure}，实际{failure}")

    if movement is not None and roots == ["episode-001"] and count == len(nodes):
        scale = movement.get("scale") if isinstance(movement, dict) else None
        if not isinstance(scale, dict):
            issues.append("未编号情绪运动缺少scale")
        else:
            legal_path_min = scale.get("minimum_legal_path_length")
            interaction_min = scale.get("interaction_min")
            interaction_max = scale.get("interaction_max")
            paths: list[list[str]] = []

            def walk(node_id: str, path: list[str]) -> None:
                current = path + [node_id]
                successors = list(nodes[node_id]["successors"])
                if not successors:
                    paths.append(current)
                    return
                for target in successors:
                    if target in nodes:
                        walk(target, current)

            walk("episode-001", [])
            for path in paths:
                ending = nodes[path[-1]]
                if isinstance(legal_path_min, int) and len(path) < legal_path_min:
                    issues.append(
                        f"结局路径短于合法下限：{path[-1]}={len(path)}<{legal_path_min}"
                    )
            graph_choice_count = sum(
                1
                for node in nodes.values()
                if "选择" in str(node["interaction"])
                and "结果" not in str(node["interaction"])
            )
            if isinstance(interaction_min, int) and graph_choice_count < interaction_min:
                issues.append(f"全图互动少于探索下限：{graph_choice_count}<{interaction_min}")
            if isinstance(interaction_max, int) and graph_choice_count > interaction_max:
                issues.append(f"全图互动多于探索上限：{graph_choice_count}>{interaction_max}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("--expected-endings", type=int)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    parser.add_argument("--movement", type=Path)
    args = parser.parse_args()
    try:
        nodes = parse(args.topology)
        movement = None
        if args.movement:
            movement = json.loads(args.movement.read_text(encoding="utf-8"))
        issues = validate(
            nodes,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
            movement,
        )
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}")
        return 1
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"PASS: {len(nodes)} nodes; one root, all reachable, acyclic, ending paths valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
