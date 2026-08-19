#!/usr/bin/env python3
"""Derive one resumable next action for the complete four-stage workflow."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from run_state import status as episode_status
from execution_result import VERSION as RESULT_VERSION
from validate_user_intent_lock import validate_contract

VERSION = "nextplay.episode-workflow-resume.v1"
DELIVERY_VERSION = "nextplay.delivery-accepted.v1"

FILE_STEPS = (
    ("user-request.md", "CAPTURE_USER_REQUEST", "STORY"),
    ("user-intent-lock.json", "BUILD_USER_INTENT_LOCK", "STORY"),
    ("creative-brief.json", "BUILD_CREATIVE_BRIEF", "STORY"),
    ("complete-story.json", "WRITE_COMPLETE_STORY", "STORY"),
    ("complete-story-review.json", "REVIEW_COMPLETE_STORY", "STORY"),
    ("mainline-decomposition.json", "BUILD_MAINLINE_DECOMPOSITION", "BRANCH"),
    ("mainline-emotional-movement.json", "BUILD_MAINLINE_EMOTIONAL_MOVEMENT", "BRANCH"),
    ("decision-fissure-audit.json", "BUILD_DECISION_FISSURES", "BRANCH"),
    ("decision-fissure-review.json", "REVIEW_DECISION_FISSURES", "BRANCH"),
    ("story-treatment.json", "BUILD_STORY_TREATMENT", "BRANCH"),
    ("story-treatment-review.json", "REVIEW_STORY_TREATMENT", "BRANCH"),
    ("topology-draft-1.md", "WRITE_FIRST_TOPOLOGY", "BRANCH"),
    ("topology.md", "REBUILD_TOPOLOGY", "BRANCH"),
    ("mainline-path.json", "BUILD_MAINLINE_PATH", "BRANCH"),
    ("route-duration.json", "VALIDATE_ROUTE_DURATION", "BRANCH"),
    ("mainline-projection-review.json", "VERIFY_MAINLINE_PROJECTION", "BRANCH"),
    ("topology-review-packet.json", "BUILD_TOPOLOGY_REVIEW_PACKET", "BRANCH"),
    ("topology-review-a.json", "REVIEW_TOPOLOGY_A", "BRANCH"),
    ("topology-review-b.json", "REVIEW_TOPOLOGY_B", "BRANCH"),
    ("synopsis-set-review.json", "BUILD_AND_REVIEW_SYNOPSIS_SET", "BRANCH"),
    ("emotional-spine.json", "PROJECT_AND_VALIDATE_EMOTIONAL_SPINE", "BRANCH"),
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


def pending_execution(root: Path) -> dict[str, Any] | None:
    """Recover the last handled failure after an environment context cut."""

    marker = root / ".execution-state.json"
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
        if (
            value.get("contract_version") == RESULT_VERSION
            and value.get("status") == "IN_PROGRESS"
            and isinstance(value.get("next_action"), dict)
            and value["next_action"].get("action")
        ):
            return {
                "contract_version": VERSION,
                "status": "IN_PROGRESS",
                "phase": "RECOVERY",
                "reason_code": value.get("reason_code"),
                "issues": value.get("issues") or [],
                "next_actions": [value["next_action"]],
            }
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return None


def waiting_user(root: Path) -> dict[str, Any] | None:
    """Only a verified conflict between current user constraints may wait."""

    if not (root / "user-intent-lock.json").is_file():
        return None
    contract, _, issues = validate_contract(root)
    if issues or contract.get("resolution_status") != "needs-user":
        return None
    conflict = contract["conflicts"][0]
    return {
        "contract_version": VERSION,
        "status": "WAITING_USER",
        "phase": "STORY",
        "reason_code": "USER_CONSTRAINT_CONFLICT",
        "question": conflict["question"],
        "options": conflict["options"],
        "constraint_ids": conflict["constraint_ids"],
        "next_actions": [],
    }


def artifact_issues(root: Path, filename: str) -> list[str]:
    """Validate an existing checkpoint instead of trusting file presence."""

    try:
        if filename == "user-request.md":
            return [] if (root / filename).read_text(encoding="utf-8").strip() else ["用户要求源为空"]
        if filename == "user-intent-lock.json":
            return validate_contract(root)[2]
        if filename == "creative-brief.json":
            from validate_creative_brief import validate_frozen
            validate_frozen(root)
        elif filename == "complete-story.json":
            from complete_story_gate import read_complete_story
            read_complete_story(root)
        elif filename == "complete-story-review.json":
            from complete_story_gate import verify
            return verify(root)
        elif filename == "mainline-decomposition.json":
            from validate_mainline_projection import decomposition_issues
            return decomposition_issues(root)[0]
        elif filename == "mainline-emotional-movement.json":
            from validate_mainline_emotional_movement import validate
            return validate(root)
        elif filename == "decision-fissure-audit.json":
            from decision_fissure_gate import read_audit
            read_audit(root)
        elif filename == "decision-fissure-review.json":
            from decision_fissure_gate import verify
            return verify(root)
        elif filename == "story-treatment.json":
            from story_treatment_gate import read_treatment
            read_treatment(root)
        elif filename == "story-treatment-review.json":
            from story_treatment_gate import verify
            return verify(root)
        elif filename == "topology-draft-1.md":
            from validate_topology import parse, validate
            return validate(parse(root / filename))
        elif filename == "topology.md":
            from validate_topology import parse, validate
            from validate_topology_revision import validate_revision
            return [
                *validate(parse(root / filename)),
                *validate_revision(root / "topology-draft-1.md", root / filename),
            ]
        elif filename in {"mainline-path.json", "mainline-projection-review.json"}:
            from validate_mainline_projection import topology_issues
            return topology_issues(root)
        elif filename == "route-duration.json":
            from validate_route_duration import validate
            return validate(root / filename, root / "topology.md")
        elif filename in {"topology-review-a.json", "topology-review-b.json"}:
            from topology_dual_review_gate import verify
            return verify(root)
        elif filename == "emotional-spine.json":
            from planning_acceptance import resolved_endings
            from validate_emotional_topology import validate_emotional_topology
            endings = resolved_endings(root)
            return validate_emotional_topology(
                root, root / "topology.md", root / filename,
                endings["major"], endings["main"], endings["expected"],
                endings["failure"], endings["small"],
            )
        elif filename == "synopsis-set-review.json":
            from synopsis_set_gate import verify
            return verify(root)
        elif filename == "planning-acceptance.json":
            from planning_acceptance import verify
            return verify(root)
        elif filename == "asset-catalog.json":
            from build_asset_catalog import build
            value = json.loads((root / filename).read_text(encoding="utf-8"))
            return [] if value == build(root) else ["资产校验目录已失效"]
        elif filename == "run-state.json":
            from run_state import load, require_current_planning
            state = load(root)
            require_current_planning(root, state)
        return []
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def status(cache_root: Path) -> dict[str, Any]:
    root = cache_root.resolve()
    waiting = waiting_user(root)
    if waiting is not None:
        return waiting
    pending = pending_execution(root)
    if pending is not None:
        return pending
    for filename, name, phase in FILE_STEPS:
        if not (root / filename).is_file():
            return {
                "contract_version": VERSION, "status": "IN_PROGRESS", "phase": phase,
                "next_actions": [action(name, phase)],
            }
        issues = artifact_issues(root, filename)
        if issues:
            return {
                "contract_version": VERSION,
                "status": "IN_PROGRESS",
                "phase": phase,
                "reason_code": "CHECKPOINT_INVALID",
                "issues": issues,
                "next_actions": [action(name, phase, repair=True)],
            }
    if not any((root / "episode-synopses").glob("episode-*.json")):
        return {
            "contract_version": VERSION, "status": "IN_PROGRESS", "phase": "BRANCH",
            "next_actions": [action("BUILD_AND_REVIEW_SYNOPSIS_SET", "BRANCH")],
        }
    episodes = episode_status(root)
    if episodes["status"] == "STOPPED":
        return {
            "contract_version": VERSION,
            "status": "STOPPED",
            "phase": "EPISODE",
            "reason_code": episodes.get("reason_code"),
            "issues": episodes.get("issues") or [],
            "next_actions": [],
        }
    if episodes["status"] != "READY_FOR_CLOSURE":
        next_item = dict(episodes["next_actions"][0])
        next_item["phase"] = "EPISODE"
        return {
            "contract_version": VERSION, "status": "IN_PROGRESS", "phase": "EPISODE",
            "next_actions": [next_item],
        }
    if delivery_is_current(root):
        return {
            "contract_version": VERSION, "status": "ACCEPTED", "phase": "FINAL",
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
        return not_accepted(__file__)
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
