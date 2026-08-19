#!/usr/bin/env python3
"""Validate the emotional spine projected after the formal topology exists."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import json
import re
from pathlib import Path

from validate_emotional_topology import validate_spine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spine", type=Path)
    parser.add_argument("--expected-nodes", type=int)
    args = parser.parse_args()
    try:
        spine = json.loads(args.spine.read_text(encoding="utf-8"))
        entries = spine.get("nodes") if isinstance(spine, dict) else None
        node_ids = [item.get("episode_id") for item in entries or [] if isinstance(item, dict)]
        issues = validate_spine(spine, node_ids)
        expected_ids = [f"episode-{index:03d}" for index in range(1, len(node_ids) + 1)]
        if node_ids != expected_ids:
            issues.append(f"情绪脊编号必须从 episode-001 连续排列：{node_ids}")
        if len(node_ids) != len(set(node_ids)) or any(
            not isinstance(node_id, str) or not re.fullmatch(r"episode-\d{3}", node_id)
            for node_id in node_ids
        ):
            issues.append("情绪脊节点编号非法或重复")
        if args.expected_nodes is not None and len(node_ids) != args.expected_nodes:
            issues.append(f"情绪脊节点数错误：期望{args.expected_nodes}，实际{len(node_ids)}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    if issues:
        print("FAIL")
        for issue in dict.fromkeys(issues):
            print(f"- {issue}")
        return not_accepted(__file__)
    print(f"PASS: {len(node_ids)} post-topology emotional states are valid")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
