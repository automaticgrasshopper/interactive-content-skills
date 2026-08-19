#!/usr/bin/env python3
"""Single source of truth for the per-episode atomic workflow."""

from __future__ import annotations

from pathlib import Path

VERSION = "nextplay.episode-action-contracts.v5"
GENERATIVE_ACTIONS = {"WRITE_COMPACT_DRAFT", "ENHANCE"}
GENERATIVE_REFERENCES = {
    "WRITE_COMPACT_DRAFT": "references/compact-draft-writer.md",
    "ENHANCE": "references/vimax-script-enhancer.md",
}
REVIEW_ACTIONS: set[str] = set()

TRANSITIONS = {
    "QUEUED": {"ADAPT": "ADAPTED"},
    "ADAPTED": {"WRITE_COMPACT_DRAFT": "COMPACT_DRAFTED"},
    "COMPACT_DRAFTED": {"VALIDATE_COMPACT_DRAFT": "COMPACT_DRAFT_VALIDATED"},
    "COMPACT_DRAFT_VALIDATED": {"ENHANCE": "ENHANCED"},
    "ENHANCED": {"VALIDATE_STRUCTURE": "STRUCTURE_VALIDATED"},
    "STRUCTURE_VALIDATED": {"ACCEPT_EPISODE": "EPISODE_ACCEPTED"},
}

def relative_outputs(action: str, episode_id: str, outcome: str = "PASS") -> tuple[str, ...]:
    if outcome != "PASS":
        raise ValueError("当前写作链不接受FAIL产物提交")
    fixed = {
        "ADAPT": (
            f"episode-adaptation-sources/{episode_id}.json",
            f"episode-story-materials/{episode_id}.json",
            f"episode-writing-inputs/{episode_id}.txt",
        ),
        "WRITE_COMPACT_DRAFT": (f"compact-drafts/{episode_id}.md",),
        "VALIDATE_COMPACT_DRAFT": (
            f"compact-draft-receipts/{episode_id}.json",
            f"enhancer-inputs/{episode_id}.txt",
        ),
        "ENHANCE": (f"enhanced-screenplays/{episode_id}.md",),
        "VALIDATE_STRUCTURE": (
            f"episodes/{episode_id}.md",
            f"episode-structure-receipts/{episode_id}.json",
        ),
        "ACCEPT_EPISODE": (f"episode-acceptance-receipts/{episode_id}.json",),
    }
    if action not in fixed:
        raise ValueError(f"未知原子动作：{action}")
    return fixed[action]

def expected_outputs(cache_root: Path, action: str, episode_id: str, outcome: str = "PASS") -> list[Path]:
    return [(cache_root / item).resolve() for item in relative_outputs(action, episode_id, outcome)]

def generative_input(cache_root: Path, action: str, episode_id: str) -> Path:
    mapping = {
        "WRITE_COMPACT_DRAFT": f"episode-writing-inputs/{episode_id}.txt",
        "ENHANCE": f"enhancer-inputs/{episode_id}.txt",
    }
    if action not in mapping:
        raise ValueError(f"该动作不是生成动作：{action}")
    return (cache_root / mapping[action]).resolve()
