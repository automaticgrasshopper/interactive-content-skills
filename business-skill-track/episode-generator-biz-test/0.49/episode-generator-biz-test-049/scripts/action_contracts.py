#!/usr/bin/env python3
"""Single source of truth for the per-episode atomic workflow."""

from __future__ import annotations

from pathlib import Path


VERSION = "nextplay.episode-action-contracts.v2"

CHILD_ACTIONS = {
    "WRITE_DRAFT",
    "ENHANCE",
    "REVIEW_DRAMA",
    "REVIEW_COLD_READ",
    "REPAIR",
}
REVIEW_ACTIONS = {"REVIEW_DRAMA", "REVIEW_COLD_READ"}

TRANSITIONS = {
    "QUEUED": {"ADAPT": "ADAPTED"},
    "ADAPTED": {"WRITE_DRAFT": "DRAFTED"},
    "DRAFTED": {"VALIDATE_DRAFT": "DRAFT_VALIDATED"},
    "DRAFT_VALIDATED": {"ENHANCE": "ENHANCED"},
    "ENHANCED": {"VALIDATE_STRUCTURE": "STRUCTURE_VALIDATED"},
    "REPAIRED": {"VALIDATE_STRUCTURE": "STRUCTURE_VALIDATED"},
    "STRUCTURE_VALIDATED": {"PREPARE_REVIEWS": "REVIEWS_PREPARED"},
    "REVIEWS_PREPARED": {
        "REVIEW_DRAMA": "REVIEWING",
        "REVIEW_COLD_READ": "REVIEWING",
    },
    "REVIEWING": {
        "REVIEW_DRAMA": "REVIEWING",
        "REVIEW_COLD_READ": "REVIEWING",
    },
    "REVIEWS_FAILED": {"MERGE_FINDINGS": "FINDINGS_MERGED"},
    "FINDINGS_MERGED": {"REPAIR": "REPAIRED"},
    "REVIEWS_PASSED": {"ACCEPT_EPISODE": "EPISODE_ACCEPTED"},
}


def relative_outputs(action: str, episode_id: str, outcome: str = "PASS") -> tuple[str, ...]:
    fixed = {
        "ADAPT": (
            f"episode-adaptation-sources/{episode_id}.json",
            f"episode-story-materials/{episode_id}.json",
            f"episode-writing-inputs/{episode_id}.txt",
        ),
        "WRITE_DRAFT": (f"screenplay-drafts/{episode_id}.md",),
        "VALIDATE_DRAFT": (
            f"screenwriter-receipts/{episode_id}.json",
            f"enhancer-inputs/{episode_id}.txt",
        ),
        "ENHANCE": (f"enhanced-screenplays/{episode_id}.md",),
        "VALIDATE_STRUCTURE": (
            f"episodes/{episode_id}.md",
            f"episode-structure-receipts/{episode_id}.json",
        ),
        "PREPARE_REVIEWS": (
            f"dramatization-plans/{episode_id}.json",
            f"review-packets/{episode_id}.dramatization.json",
            f"review-packets/{episode_id}.cold-read.json",
        ),
        "MERGE_FINDINGS": (f"merged-review-findings/{episode_id}.json",),
        "REPAIR": (
            f"enhanced-screenplays/{episode_id}.md",
            f"episodes/{episode_id}.md",
            f"review-repair-receipts/{episode_id}.json",
        ),
        "ACCEPT_EPISODE": (f"episode-acceptance-receipts/{episode_id}.json",),
    }
    if action == "REVIEW_DRAMA":
        return (
            f"dramatization-receipts/{episode_id}.json"
            if outcome == "PASS"
            else f"review-findings/{episode_id}.dramatization.json",
        )
    if action == "REVIEW_COLD_READ":
        return (
            f"episode-quality-receipts/{episode_id}.json"
            if outcome == "PASS"
            else f"review-findings/{episode_id}.cold-read.json",
        )
    if action not in fixed:
        raise ValueError(f"未知原子动作：{action}")
    return fixed[action]


def expected_outputs(cache_root: Path, action: str, episode_id: str, outcome: str = "PASS") -> list[Path]:
    return [(cache_root / item).resolve() for item in relative_outputs(action, episode_id, outcome)]


def child_input(cache_root: Path, action: str, episode_id: str) -> Path:
    mapping = {
        "WRITE_DRAFT": f"episode-writing-inputs/{episode_id}.txt",
        "ENHANCE": f"enhancer-inputs/{episode_id}.txt",
        "REVIEW_DRAMA": f"review-packets/{episode_id}.dramatization.json",
        "REVIEW_COLD_READ": f"review-packets/{episode_id}.cold-read.json",
        "REPAIR": f"review-repair-inputs/{episode_id}.txt",
    }
    if action not in mapping:
        raise ValueError(f"该动作不是子Agent动作：{action}")
    return (cache_root / mapping[action]).resolve()
