#!/usr/bin/env python3
"""Derive one resumable next action for the complete four-stage workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from run_state import status as episode_status

VERSION = "nextplay.episode-workflow-resume.v1"
DELIVERY_VERSION = "nextplay.delivery-accepted.v1"

FILE_STEPS = (
    ("user-request.md", "CAPTURE_USER_REQUEST", "STORY"),
    ("user-intent-lock.json", "BUILD_USER_INTENT_LOCK", "STORY"),
    ("creative-brief.json", "BUILD_CREATIVE_BRIEF", "STORY"),
    ("complete-story.json", "WRITE_COMPLETE_STORY", "STORY"),
    ("complete-story-review.json", "REVIEW_COMPLETE_STORY", "STORY"),
    ("mainline-decomposition.json", "BUILD_MAINLINE_DECOMPOSITION", "BRANCH"),
    ("mainline-path.json", "BUILD_MAINLINE_PATH", "BRANCH"),
    ("mainline-projection-review.json", "VERIFY_MAINLINE_PROJECTION", "BRANCH"),
    ("decision-fissure-audit.json", "BUILD_DECISION_FISSURES", "BRANCH"),
    ("decision-fissure-review.json", "REVIEW_DECISION_FISSURES", "BRANCH"),
    ("story-treatment.json", "BUILD_STORY_TREATMENT", "BRANCH"),
    ("story-treatment-review.json", "REVIEW_STORY_TREATMENT", "BRANCH"),
    ("topology-draft-1.md", "WRITE_FIRST_TOPOLOGY", "BRANCH"),
    ("topology.md", "REBUILD_TOPOLOGY", "BRANCH"),
    ("route-duration.json", "VALIDATE_ROUTE_DURATION", "BRANCH"),
    ("topology-review-packet.json", "BUILD_TOPOLOGY_REVIEW_PACKET", "BRANCH"),
    ("topology-review-a.json", "REVIEW_TOPOLOGY_A", "BRANCH"),
    ("topology-review-b.json", "REVIEW_TOPOLOGY_B", "BRANCH"),
    ("emotional-spine.json", "PROJECT_EMOTIONAL_SPINE", "BRANCH"),
    ("synopsis-set-review.json", "BUILD_AND_REVIEW_SYNOPSIS_SET", "BRANCH"),
    ("planning-acceptance.json", "ACCEPT_PLANNING", "BRANCH"),
    ("asset-catalog.json", "BUILD_ASSET_CATALOG", "EPISODE"),
    ("character-introductions.json", "INITIALIZE_CHARACTER_INTRODUCTIONS", "EPISODE"),
    ("run-state.json", "INITIALIZE_EPISODE_RUN", "EPISODE"),
)


def action(name: str, phase: str, **extra: Any) -> dict[str, Any]:
    return {
        "action": name, "phase": phase, "execution_mode": "current_task",
        "instruction": "读取SKILL.md中当前阶段的Reference路由，执行本动作；安全提交后再次运行workflow_state.py。",
        **extra,
    }


def delivery_is_current(root: Path) -> bool:
    try:
        value = json.loads((root / "delivery-accepted.json").read_text(encoding="utf-8"))
        paths = {
            "business_output_sha256": root / "business-output.json",
            "completion_receipt_sha256": root / "completion-receipt.json",
            "handoff_sha256": root / "episode-handoff.json",
        }
        return value.get("contract_version") == DELIVERY_VERSION and value.get("status") == "PASS" and all(
            path.is_file() and value.get(field) == hashlib.sha256(path.read_bytes()).hexdigest()
            for field, path in paths.items()
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def status(cache_root: Path) -> dict[str, Any]:
    root = cache_root.resolve()
    for filename, name, phase in FILE_STEPS:
        if not (root / filename).is_file():
            return {
                "contract_version": VERSION, "status": "IN_PROGRESS", "phase": phase,
                "next_actions": [action(name, phase)],
            }
    if not any((root / "episode-synopses").glob("episode-*.json")):
        return {
            "contract_version": VERSION, "status": "IN_PROGRESS", "phase": "BRANCH",
            "next_actions": [action("BUILD_AND_REVIEW_SYNOPSIS_SET", "BRANCH")],
        }
    episodes = episode_status(root)
    if episodes["status"] != "READY_FOR_CLOSURE":
        next_item = dict(episodes["next_actions"][0])
        next_item["phase"] = "EPISODE"
        return {
            "contract_version": VERSION, "status": "IN_PROGRESS", "phase": "EPISODE",
            "next_actions": [next_item],
        }
    if delivery_is_current(root):
        return {
            "contract_version": VERSION, "status": "COMPLETE", "phase": "FINAL",
            "next_actions": [],
        }
    required = (root / "business-output.json", root / "completion-receipt.json", root / "episode-handoff.json")
    next_name = "VERIFY_DELIVERABLE" if all(path.is_file() for path in required) else "ASSEMBLE_DELIVERABLE"
    return {
        "contract_version": VERSION, "status": "IN_PROGRESS", "phase": "FINAL",
        "next_actions": [action(next_name, "FINAL")],
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
