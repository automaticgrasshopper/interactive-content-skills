#!/usr/bin/env python3
"""Bind a completed Biz run to its private dependencies and business JSON."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "nextplay.episode-completion.v6"


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
    }
    for name in (
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
        ("dramatization-plans", ".json"),
        ("episodes", ".md"),
        ("dramatization-reviews", ".json"),
        ("quality-reviews", ".json"),
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
