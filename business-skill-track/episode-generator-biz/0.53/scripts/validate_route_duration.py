#!/usr/bin/env python3
"""Validate exact route enumeration and internal duration accounting without a cap."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import json
from pathlib import Path
from typing import Any

from validate_topology import parse


CONTRACT_VERSION = "nextplay.route-duration.v2"
ROOT_FIELDS = {"contract_version", "unit", "mainline_path", "node_minutes", "paths"}
PATH_FIELDS = {"ending_id", "node_ids", "total_minutes"}

def graph_paths(nodes: dict[str, dict[str, object]]) -> list[list[str]]:
    result: list[list[str]] = []
    def walk(node_id: str, path: list[str]) -> None:
        current = path + [node_id]
        successors = list(nodes[node_id]["successors"])
        if not successors:
            result.append(current)
            return
        for target in successors:
            walk(str(target), current)
    walk("episode-001", [])
    return sorted(result)


def validate(
    duration_path: Path,
    topology_path: Path,
) -> list[str]:
    issues: list[str] = []
    try:
        data = json.loads(duration_path.read_text(encoding="utf-8"))
        nodes = parse(topology_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        return ["路线时长根字段错误"]
    if data.get("contract_version") != CONTRACT_VERSION or data.get("unit") != "minutes":
        issues.append("路线记账合同版本或单位错误")
    minutes = data.get("node_minutes")
    if not isinstance(minutes, dict) or set(minutes) != set(nodes):
        issues.append("node_minutes必须逐一覆盖全部拓扑节点")
        minutes = {}
    for node_id, value in minutes.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            issues.append(f"节点预计时长必须为正数：{node_id}")
    expected_paths = graph_paths(nodes)
    supplied = data.get("paths")
    supplied_by_nodes: dict[tuple[str, ...], dict[str, Any]] = {}
    if not isinstance(supplied, list):
        issues.append("paths必须为数组")
        supplied = []
    for item in supplied:
        if not isinstance(item, dict) or set(item) != PATH_FIELDS or not isinstance(item.get("node_ids"), list):
            issues.append("路线记录字段错误")
            continue
        key = tuple(str(value) for value in item["node_ids"])
        if key in supplied_by_nodes:
            issues.append(f"重复路线：{key}")
        supplied_by_nodes[key] = item
    if set(supplied_by_nodes) != {tuple(path) for path in expected_paths}:
        issues.append("paths没有精确枚举全部入口到结局路线")
    for path in expected_paths:
        item = supplied_by_nodes.get(tuple(path))
        if not item or set(minutes) != set(nodes):
            continue
        total = round(sum(float(minutes[node]) for node in path), 3)
        if item.get("ending_id") != path[-1] or not isinstance(item.get("total_minutes"), (int, float)):
            issues.append(f"路线结局或总时长字段错误：{path[-1]}")
            continue
        if abs(float(item["total_minutes"]) - total) > 0.001:
            issues.append(f"路线总时长计算错误：{path[-1]}")
    mainline = data.get("mainline_path")
    if not isinstance(mainline, list) or tuple(mainline) not in {tuple(path) for path in expected_paths}:
        issues.append("mainline_path必须是实际入口到结局路线")
    elif "主结局" not in str(nodes[str(mainline[-1])]["interaction"]):
        issues.append("mainline_path必须到达冻结完整故事的主结局")
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("duration", type=Path)
    parser.add_argument("topology", type=Path)
    args = parser.parse_args()
    issues = validate(args.duration, args.topology)
    if issues:
        print("FAIL")
        for issue in issues: print(f"- {issue}")
        return not_accepted(__file__)
    print("PASS: every route is enumerated; no upstream duration cap is applied")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
