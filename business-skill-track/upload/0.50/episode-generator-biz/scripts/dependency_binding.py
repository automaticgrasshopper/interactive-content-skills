#!/usr/bin/env python3
"""Stable content bindings for stage-two and per-episode artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_leaves(cache_root: Path) -> dict[str, Any]:
    receipt = json.loads((cache_root / "stage-two-acceptance.json").read_text(encoding="utf-8"))
    leaves = receipt.get("content_leaves")
    if not isinstance(leaves, dict) or not isinstance(leaves.get("episodes"), dict):
        raise ValueError("阶段二回执缺少稳定内容叶")
    return leaves


def stage_two_content_sha256(cache_root: Path) -> str:
    value = str(load_leaves(cache_root).get("content_sha256") or "")
    if len(value) != 64:
        raise ValueError("阶段二内容指纹无效")
    return value


def episode_dependency_sha256(cache_root: Path, episode_id: str) -> str:
    leaves = load_leaves(cache_root)
    synopsis = str((leaves.get("episodes") or {}).get(episode_id) or "")
    if len(synopsis) != 64:
        raise ValueError(f"阶段二缺少分集内容叶：{episode_id}")
    return digest_value({
        "global": leaves.get("global"),
        "episode_id": episode_id,
        "synopsis_sha256": synopsis,
    })
