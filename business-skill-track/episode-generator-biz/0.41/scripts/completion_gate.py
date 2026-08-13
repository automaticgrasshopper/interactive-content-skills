#!/usr/bin/env python3
"""Bind a completed Biz run to its private dependencies and business JSON."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "nextplay.episode-completion.v12"
HANDOFF_VERSION = "nextplay.episode-handoff.v1"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def dependency_files(
    cache_root: Path,
    business_path: Path,
    asset_catalog_path: Path,
    character_introductions_path: Path,
    spine_path: Path,
) -> dict[str, Path]:
    result = {
        "business-json": business_path,
        "cache/run-basis.json": cache_root / "run-basis.json",
        "cache/unnumbered-emotional-movement.json": cache_root / "unnumbered-emotional-movement.json",
        "asset-catalog": asset_catalog_path,
        "character-introductions": character_introductions_path,
        "emotional-spine": spine_path,
        "cache/stage-two-input.json": cache_root / "stage-two-input.json",
        "cache/mainline-decomposition.json": cache_root / "mainline-decomposition.json",
        "cache/mainline-path.json": cache_root / "mainline-path.json",
    }
    for name in (
        "mainline-story.json",
        "mainline-story-review.json",
        "decision-fissure-audit.json",
        "decision-fissure-review.json",
        "route-duration.json",
        "story-treatment.json",
        "story-treatment-review.json",
        "topology.md",
        "synopsis-set-review.json",
        "user-request.md",
        "user-intent-lock.json",
        "user-intent-review.json",
    ):
        result[f"cache/{name}"] = cache_root / name
    for directory, suffix in (
        ("episode-synopses", ".json"),
        ("episode-adaptation-sources", ".json"),
        ("episode-story-materials", ".json"),
        ("episode-writing-inputs", ".txt"),
        ("enhancer-inputs", ".txt"),
        ("screenplay-drafts", ".md"),
        ("screenwriter-receipts", ".json"),
        ("enhanced-screenplays", ".md"),
        ("dramatization-receipts", ".json"),
        ("episode-quality-receipts", ".json"),
        ("episodes", ".md"),
    ):
        folder = cache_root / directory
        if folder.is_dir():
            for path in sorted(folder.glob(f"*{suffix}")):
                result[f"cache/{directory}/{path.name}"] = path
    return result


def artifact_hashes(paths: dict[str, Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for label, path in sorted(paths.items()):
        if not path.is_file():
            raise ValueError(f"完成凭证缺少依赖：{label}")
        hashes[label] = sha256_bytes(path.read_bytes())
    return hashes


def validate_episode_artifact_closure(cache_root: Path) -> None:
    synopsis_dir = cache_root / "episode-synopses"
    episode_ids = sorted(path.stem for path in synopsis_dir.glob("episode-*.json"))
    if not episode_ids:
        raise ValueError("完成凭证缺少全体分集梗概")
    required = {
        "episode-adaptation-sources": ".json",
        "episode-story-materials": ".json",
        "episode-writing-inputs": ".txt",
        "screenplay-drafts": ".md",
        "screenwriter-receipts": ".json",
        "enhancer-inputs": ".txt",
        "enhanced-screenplays": ".md",
        "dramatization-receipts": ".json",
        "episode-quality-receipts": ".json",
        "episodes": ".md",
    }
    for directory, suffix in required.items():
        folder = cache_root / directory
        actual = sorted(path.stem for path in folder.glob(f"episode-*{suffix}"))
        if actual != episode_ids:
            missing = sorted(set(episode_ids) - set(actual))
            extra = sorted(set(actual) - set(episode_ids))
            raise ValueError(f"分集产物闭包不完整：{directory} 缺少{missing}，多余{extra}")


def make_receipt(
    cache_root: Path,
    business_path: Path,
    asset_catalog_path: Path,
    character_introductions_path: Path,
    spine_path: Path,
    skill_version: str,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "skill_version": skill_version,
        "artifacts": artifact_hashes(
            dependency_files(
                cache_root,
                business_path,
                asset_catalog_path,
                character_introductions_path,
                spine_path,
            )
        ),
    }


def validate_receipt(
    receipt_path: Path,
    cache_root: Path,
    business_path: Path,
    asset_catalog_path: Path,
    character_introductions_path: Path,
    spine_path: Path,
    skill_version: str,
) -> list[str]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        expected = make_receipt(
            cache_root,
            business_path,
            asset_catalog_path,
            character_introductions_path,
            spine_path,
            skill_version,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"完成凭证不可用：{error}"]
    if receipt != expected:
        return ["完成凭证与当前冻结基础、剧本、复检材料或业务JSON不一致"]
    return []


def make_handoff(
    cache_root: Path,
    business_path: Path,
    receipt_path: Path,
    skill_version: str,
) -> dict[str, Any]:
    validate_episode_artifact_closure(cache_root)
    business = json.loads(business_path.read_text(encoding="utf-8"))
    topology_text = (cache_root / "topology.md").read_text(encoding="utf-8")
    return {
        "contract_version": HANDOFF_VERSION,
        "capability_id": "episode-generator-biz",
        "skill_version": skill_version,
        "business_output": {
            "path": str(business_path.resolve()),
            "sha256": sha256_bytes(business_path.read_bytes()),
        },
        "completion_receipt": {
            "path": str(receipt_path.resolve()),
            "sha256": sha256_bytes(receipt_path.read_bytes()),
            "contract_version": CONTRACT_VERSION,
        },
        "resolved_counts": {
            "episodes": len(business.get("分集列表") or []),
            "main_endings": topology_text.count("主要正式结局") + topology_text.count("主要失败结局"),
            "minor_endings": topology_text.count("独立小结局"),
        },
        "status": {
            "business_schema": "passed",
            "skill_acceptance": "verified",
            "project_projection": "not_performed",
        },
    }


def validate_handoff(
    handoff_path: Path,
    cache_root: Path,
    business_path: Path,
    receipt_path: Path,
    skill_version: str,
) -> list[str]:
    try:
        actual = json.loads(handoff_path.read_text(encoding="utf-8"))
        expected = make_handoff(cache_root, business_path, receipt_path, skill_version)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"交接清单不可用：{error}"]
    if actual != expected:
        return ["交接清单与当前业务JSON、完成凭证或拓扑统计不一致"]
    return []
