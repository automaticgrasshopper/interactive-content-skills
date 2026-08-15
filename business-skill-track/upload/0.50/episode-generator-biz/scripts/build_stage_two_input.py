#!/usr/bin/env python3
"""Build a stage-two generation view without upstream scale suggestions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from validate_run_basis import load_object, validate_basis
from validate_user_intent_lock import validate_contract


CONTRACT_VERSION = "nextplay.episode-stage-two-input.v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def from_sources(cache_root: Path) -> dict[str, Any]:
    contract, contract_sha, intent_issues = validate_contract(cache_root)
    if intent_issues:
        raise ValueError("；".join(dict.fromkeys(intent_issues)))

    basis_path = cache_root / "run-basis.json"
    assets_path = cache_root / "asset-catalog.json"
    basis = load_object(basis_path, "运行基础")
    assets = load_object(assets_path, "资产目录")
    story = dict(basis["story"])
    story.pop("node_count_hint", None)
    story.pop("duration", None)
    constraints = [
        item
        for item in contract["constraints"]
        if isinstance(item, dict) and item.get("required") is True
    ]
    packet = {
        "contract_version": CONTRACT_VERSION,
        "run_basis_sha256": sha256_bytes(basis_path.read_bytes()),
        "asset_catalog_sha256": sha256_bytes(assets_path.read_bytes()),
        "user_intent_contract_sha256": contract_sha,
        "story": story,
        "ending_plan": basis["ending_plan"],
        "characters": basis["characters"],
        "assets": assets,
        "user_constraints": constraints,
    }
    serialized = json.dumps(packet, ensure_ascii=False)
    if "node_count_hint" in serialized:
        raise ValueError("阶段二生成包泄露了上游节点建议")
    if "duration" in packet["story"]:
        raise ValueError("阶段二生成包泄露了上游推荐时长")
    return packet


def build(cache_root: Path) -> dict[str, Any]:
    issues = validate_basis(cache_root, require_empty_introductions=True)
    if issues:
        raise ValueError("；".join(dict.fromkeys(issues)))
    return from_sources(cache_root)


def validate_frozen(cache_root: Path) -> dict[str, Any]:
    path = cache_root / "stage-two-input.json"
    if not path.is_file():
        raise ValueError("缺少阶段二生成包：stage-two-input.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = from_sources(cache_root)
    if value != expected:
        raise ValueError("阶段二生成包与当前冻结基础不一致或含有额外字段")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        value = json.dumps(build(args.cache_root), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(value, encoding="utf-8")
        else:
            print(value, end="")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print("PASS: stage-two generation view excludes upstream scale suggestions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
