#!/usr/bin/env python3
"""Validate a user-locked decision graph without depending on node IDs or prose."""

from __future__ import annotations

from collections import deque
from typing import Any


LOCK_NODE_KINDS = {"start", "choice", "ending"}
ENDING_TYPES = {"main", "expected", "failure", "small", None}


def shape_lock_issues(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict) or set(value) != {"nodes", "edges"}:
        return ["用户形状锁字段错误"]
    nodes = value.get("nodes")
    edges = value.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not nodes:
        return ["用户形状锁必须提供非空nodes和edges数组"]
    by_id: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or set(node) != {"lock_id", "kind", "ending_type"}:
            errors.append(f"用户形状锁节点字段错误：{index}")
            continue
        node_id = node.get("lock_id")
        kind = node.get("kind")
        ending_type = node.get("ending_type")
        if not isinstance(node_id, str) or not node_id.strip() or node_id in by_id:
            errors.append(f"用户形状锁节点编号非法或重复：{node_id}")
            continue
        if kind not in LOCK_NODE_KINDS:
            errors.append(f"用户形状锁节点类型非法：{node_id}")
        if kind == "ending":
            if ending_type not in ENDING_TYPES:
                errors.append(f"用户形状锁结局类型非法：{node_id}")
        elif ending_type is not None:
            errors.append(f"非结局结构节点不得填写结局类型：{node_id}")
        by_id[node_id] = node
    starts = [node_id for node_id, node in by_id.items() if node.get("kind") == "start"]
    if len(starts) != 1:
        errors.append("用户形状锁必须且只能有一个start节点")
    successors = {node_id: [] for node_id in by_id}
    seen: set[tuple[str, str]] = set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict) or set(edge) != {"source", "target"}:
            errors.append(f"用户形状锁边字段错误：{index}")
            continue
        source = edge.get("source")
        target = edge.get("target")
        pair = (source, target)
        if source not in by_id or target not in by_id or source == target or pair in seen:
            errors.append(f"用户形状锁边非法或重复：{source}->{target}")
            continue
        seen.add(pair)
        successors[source].append(target)
    if starts:
        reached: set[str] = set()
        queue = deque(starts)
        while queue:
            current = queue.popleft()
            if current in reached:
                continue
            reached.add(current)
            queue.extend(successors.get(current, []))
        if reached != set(by_id):
            errors.append("用户形状锁含有从start不可达的节点")
    if any(successors[node_id] for node_id, node in by_id.items() if node.get("kind") == "ending"):
        errors.append("用户形状锁中的结局不得有后继")
    return list(dict.fromkeys(errors))


def _node_kind(node: dict[str, Any]) -> tuple[str, str | None]:
    if node.get("是否结局") is True:
        return "ending", node.get("ending_type")
    interaction = node.get("互动节点")
    if isinstance(interaction, dict) and interaction.get("是否为分支节点") is True:
        return "choice", None
    return "story", None


def decision_graph(route: Any) -> dict[str, Any]:
    raw_nodes = route.get("nodes") if isinstance(route, dict) else None
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("候选路线缺少节点")
    by_id = {node.get("node_id"): node for node in raw_nodes if isinstance(node, dict)}
    if None in by_id or len(by_id) != len(raw_nodes):
        raise ValueError("候选路线节点编号非法")
    predecessors = {node_id: [] for node_id in by_id}
    for source, node in by_id.items():
        for target in node.get("后续节点编号列表", []):
            if target not in by_id:
                raise ValueError("候选路线含非法后继")
            predecessors[target].append(source)
    roots = [node_id for node_id, parents in predecessors.items() if not parents]
    if len(roots) != 1:
        raise ValueError("候选路线没有唯一入口")
    significant = {
        node_id for node_id, node in by_id.items()
        if _node_kind(node)[0] in {"choice", "ending"}
    }
    graph_nodes = [{"id": "__start__", "kind": "start", "ending_type": None}]
    graph_nodes.extend({
        "id": node_id,
        "kind": _node_kind(by_id[node_id])[0],
        "ending_type": _node_kind(by_id[node_id])[1],
    } for node_id in sorted(significant))

    def next_significant(starts: list[str]) -> set[str]:
        found: set[str] = set()
        queue = deque(starts)
        seen: set[str] = set()
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            if current in significant:
                found.add(current)
            else:
                queue.extend(by_id[current].get("后续节点编号列表", []))
        return found

    graph_edges = {("__start__", target) for target in next_significant([roots[0]])}
    for source in significant:
        graph_edges.update(
            (source, target)
            for target in next_significant(list(by_id[source].get("后续节点编号列表", [])))
        )
    return {"nodes": graph_nodes, "edges": graph_edges}


def route_satisfies_exact_lock(route: Any, lock: Any) -> bool:
    if shape_lock_issues(lock):
        return False
    try:
        candidate = decision_graph(route)
    except (KeyError, TypeError, ValueError):
        return False
    lock_nodes = lock["nodes"]
    candidate_nodes = candidate["nodes"]
    lock_edges = {(edge["source"], edge["target"]) for edge in lock["edges"]}
    candidate_edges = set(candidate["edges"])
    if len(lock_nodes) != len(candidate_nodes) or len(lock_edges) != len(candidate_edges):
        return False
    lock_by_id = {node["lock_id"]: node for node in lock_nodes}
    candidate_by_id = {node["id"]: node for node in candidate_nodes}
    ordered = sorted(
        lock_by_id,
        key=lambda node_id: (
            lock_by_id[node_id]["kind"] != "start",
            -sum(node_id in edge for edge in lock_edges),
        ),
    )
    mapping: dict[str, str] = {}
    used: set[str] = set()

    def compatible(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
        if expected["kind"] != actual["kind"]:
            return False
        ending_type = expected.get("ending_type")
        return ending_type is None or ending_type == actual.get("ending_type")

    def search(index: int) -> bool:
        if index == len(ordered):
            return {(mapping[a], mapping[b]) for a, b in lock_edges} == candidate_edges
        lock_id = ordered[index]
        for candidate_id, actual in candidate_by_id.items():
            if candidate_id in used or not compatible(lock_by_id[lock_id], actual):
                continue
            mapping[lock_id] = candidate_id
            used.add(candidate_id)
            if all(
                a not in mapping or b not in mapping or (mapping[a], mapping[b]) in candidate_edges
                for a, b in lock_edges
            ) and search(index + 1):
                return True
            used.remove(candidate_id)
            mapping.pop(lock_id, None)
        return False

    return search(0)
