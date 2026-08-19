#!/usr/bin/env python3
"""Single source of truth for the per-episode atomic workflow."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

VERSION = "nextplay.episode-action-contracts.v6"
GENERATIVE_ACTIONS = {"WRITE_EPISODE", "REVIEW_EPISODE"}
GENERATIVE_REFERENCES = {
    "WRITE_EPISODE": "references/vimax-screenwriter.md",
    "REVIEW_EPISODE": "references/episode-quality-review-lite.md",
}
REVIEW_ACTIONS = {"REVIEW_EPISODE"}

TRANSITIONS = {
    "QUEUED": {"ADAPT": "ADAPTED"},
    "ADAPTED": {"WRITE_EPISODE": "SCREENPLAY_WRITTEN"},
    "SCREENPLAY_WRITTEN": {"VALIDATE_STRUCTURE": "STRUCTURE_VALIDATED"},
    "STRUCTURE_VALIDATED": {"REVIEW_EPISODE": "QUALITY_REVIEWED"},
    "QUALITY_REVIEWED": {"ACCEPT_EPISODE": "EPISODE_ACCEPTED"},
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
        "WRITE_EPISODE": (f"screenplays/{episode_id}.md",),
        "VALIDATE_STRUCTURE": (
            f"episodes/{episode_id}.md",
            f"episode-structure-receipts/{episode_id}.json",
            f"episode-review-packets/{episode_id}.json",
        ),
        "REVIEW_EPISODE": (
            f"episode-review-candidates/{episode_id}.json",
            f"episode-quality-receipts/{episode_id}.json",
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
        "WRITE_EPISODE": f"episode-writing-inputs/{episode_id}.txt",
        "REVIEW_EPISODE": f"episode-review-packets/{episode_id}.json",
    }
    if action not in mapping:
        raise ValueError(f"该动作不是生成动作：{action}")
    if action == "WRITE_EPISODE":
        base = (cache_root / mapping[action]).resolve()
        findings_path = cache_root / "episode-review-findings" / f"{episode_id}.json"
        rewrite_path = cache_root / "episode-rewrite-inputs" / f"{episode_id}.txt"
        try:
            findings = json.loads(findings_path.read_text(encoding="utf-8"))
            screenplay = cache_root / "screenplays" / f"{episode_id}.md"
            if (
                findings.get("episode_id") == episode_id
                and findings.get("status") == "FAIL"
                and findings.get("base_input_sha256") == hashlib.sha256(base.read_bytes()).hexdigest()
                and screenplay.is_file()
                and findings.get("failed_screenplay_sha256") == hashlib.sha256(screenplay.read_bytes().strip()).hexdigest()
                and rewrite_path.is_file()
            ):
                return rewrite_path.resolve()
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return (cache_root / mapping[action]).resolve()
