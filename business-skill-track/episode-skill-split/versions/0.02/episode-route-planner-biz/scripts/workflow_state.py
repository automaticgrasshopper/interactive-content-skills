#!/usr/bin/env python3
"""Derive the single next action for the route-only planning workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VERSION = "nextplay.route-workflow-resume.v1"
FILE_STEPS = (
    ("user-request.md", "CAPTURE_USER_REQUEST"),
    ("user-intent-lock.json", "BUILD_USER_INTENT_LOCK"),
    ("creative-brief.json", "BUILD_CREATIVE_BRIEF"),
    ("complete-story.json", "WRITE_COMPLETE_STORY"),
    ("complete-story-review.json", "REVIEW_COMPLETE_STORY"),
    ("mainline-decomposition.json", "BUILD_MAINLINE_DECOMPOSITION"),
    ("mainline-emotional-movement.json", "BUILD_MAINLINE_EMOTIONAL_MOVEMENT"),
    ("decision-fissure-audit.json", "BUILD_DECISION_FISSURES"),
    ("decision-fissure-review.json", "REVIEW_DECISION_FISSURES"),
    ("story-treatment.json", "BUILD_STORY_TREATMENT"),
    ("story-treatment-review.json", "REVIEW_STORY_TREATMENT"),
    ("topology-draft-1.json", "WRITE_FIRST_TOPOLOGY"),
    ("topology-draft-2.json", "WRITE_SECOND_TOPOLOGY"),
    ("topology-comparison-packet.json", "BUILD_BLIND_COMPARISON_PACKET"),
    ("topology-comparison-verdict.json", "COMPARE_TOPOLOGIES_ONCE"),
    ("topology-selection.json", "SEAL_TOPOLOGY_SELECTION"),
    ("route-candidate.json", "MATERIALIZE_SELECTED_TOPOLOGY"),
    ("topology-review-packet.json", "BUILD_TOPOLOGY_REVIEW_PACKET"),
    ("topology-review-a.json", "REVIEW_TOPOLOGY_A"),
    ("topology-review-b.json", "REVIEW_TOPOLOGY_B"),
    ("emotional-spine.json", "PROJECT_EMOTIONAL_SPINE"),
    ("route-material-review.json", "REVIEW_ROUTE_MATERIAL_SET"),
    ("planning-acceptance.json", "ACCEPT_PLANNING"),
)


def action(name: str) -> dict[str, Any]:
    return {
        "action": name,
        "phase": "BRANCH",
        "execution_mode": "current_task",
        "instruction": "只执行本动作；安全落盘后再次运行workflow_state.py。不得提前创建后续文件。",
    }


def status(cache_root: Path) -> dict[str, Any]:
    root = cache_root.resolve()
    first_missing = next((index for index, (name, _) in enumerate(FILE_STEPS) if not (root / name).is_file()), None)
    if first_missing is None:
        return {"contract_version": VERSION, "status": "COMPLETE", "phase": "BRANCH", "next_actions": []}
    future = [name for name, _ in FILE_STEPS[first_missing + 1:] if (root / name).exists()]
    if future:
        raise ValueError("发现越过当前阶段提前创建的规划产物：" + "、".join(future))
    name = FILE_STEPS[first_missing][1]
    return {
        "contract_version": VERSION,
        "status": "IN_PROGRESS",
        "phase": "BRANCH",
        "next_actions": [action(name)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        value = status(args.cache_root)
        if value["status"] == "IN_PROGRESS" and len(value["next_actions"]) != 1:
            raise ValueError("IN_PROGRESS必须且只能给出一个串行next_action")
        print(json.dumps(value, ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
