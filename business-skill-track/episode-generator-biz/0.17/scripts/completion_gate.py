#!/usr/bin/env python3
"""Bind a completed episode run to its private, public, and business artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from validate_and_assemble_scripts import build_flowchart, build_structure, section, subsection


CONTRACT_VERSION = "nextplay.episode-completion.v1"
PUBLIC_FILES = ("episode-script.md", "episode-structure.md", "episode-flowchart.svg")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def expected_public_contents(
    cache_root: Path,
    nodes: dict[str, dict[str, object]],
) -> dict[str, str]:
    scripts: list[str] = []
    synopses: dict[str, str] = {}
    for node_id in nodes:
        text = (cache_root / "episodes" / f"{node_id}.md").read_text(
            encoding="utf-8"
        ).strip()
        scripts.append(text)
        synopses[node_id] = subsection(section(text, "分集剧本"), "单集梗概")
    return {
        "episode-script.md": "\n\n---\n\n".join(scripts) + "\n",
        "episode-structure.md": build_structure(nodes, synopses),
        "episode-flowchart.svg": build_flowchart(nodes),
    }


def validate_public_bundle(
    cache_root: Path,
    public_dir: Path,
    nodes: dict[str, dict[str, object]],
) -> list[str]:
    issues: list[str] = []
    if not public_dir.is_dir():
        return ["三个公开文件尚未整组生成"]
    actual_names = sorted(item.name for item in public_dir.iterdir())
    if actual_names != sorted(PUBLIC_FILES):
        issues.append("公开目录必须且只能包含三个固定文件")
        return issues
    try:
        expected = expected_public_contents(cache_root, nodes)
    except (OSError, ValueError) as error:
        return [f"无法从当前冻结结果重建公开文件：{error}"]
    for name, content in expected.items():
        path = public_dir / name
        try:
            actual = path.read_text(encoding="utf-8")
        except OSError as error:
            issues.append(f"无法读取公开文件{name}：{error}")
            continue
        if actual != content:
            issues.append(f"公开文件与当前冻结结果不一致：{name}")
    return issues


def dependency_files(
    cache_root: Path,
    public_dir: Path,
    business_path: Path,
    asset_catalog_path: Path,
    character_introductions_path: Path,
    spine_path: Path,
) -> dict[str, Path]:
    result = {
        "business-json": business_path,
        "asset-catalog": asset_catalog_path,
        "character-introductions": character_introductions_path,
        "emotional-spine": spine_path,
    }
    for name in ("topology.md", "user-request.md", "user-intent-lock.json", "user-intent-review.json"):
        result[f"cache/{name}"] = cache_root / name
    for directory, suffix in (("episodes", ".md"), ("quality-reviews", ".json")):
        folder = cache_root / directory
        if folder.is_dir():
            for path in sorted(folder.glob(f"*{suffix}")):
                result[f"cache/{directory}/{path.name}"] = path
    for name in PUBLIC_FILES:
        result[f"public/{name}"] = public_dir / name
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
    public_dir: Path,
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
                public_dir,
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
    public_dir: Path,
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
            public_dir,
            business_path,
            asset_catalog_path,
            character_introductions_path,
            spine_path,
            skill_version,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"完成凭证不可用：{error}"]
    if receipt != expected:
        return ["完成凭证与当前剧本、公开文件或业务JSON不一致"]
    return []
