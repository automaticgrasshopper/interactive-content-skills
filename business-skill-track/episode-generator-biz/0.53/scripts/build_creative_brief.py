#!/usr/bin/env python3
"""Project only user-visible upstream fields into the 0.53 creative brief."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import json
from pathlib import Path
from typing import Any

from validate_creative_brief import CONTRACT_VERSION, validate_value
from validate_user_intent_lock import validate_contract


ASSET_TYPES = ("characters", "scenes", "props")


def optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def asset_projection(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = optional_text(item.get("name"))
        description = optional_text(item.get("description"))
        if name and description:
            result.append({"name": name, "description": description})
    return result


def project(visible: dict[str, Any], contract: dict[str, Any], contract_sha: str) -> dict[str, Any]:
    assets = visible.get("assets") if isinstance(visible.get("assets"), dict) else {}
    return {
        "contract_version": CONTRACT_VERSION,
        "user_intent_contract_sha256": contract_sha,
        "title": optional_text(visible.get("title")) or "",
        "logline": optional_text(visible.get("logline")),
        "story_description": optional_text(visible.get("story_description")) or "",
        "story_volume": optional_text(visible.get("story_volume")),
        "assets": {kind: asset_projection(assets.get(kind)) for kind in ASSET_TYPES},
        "user_constraints": [
            item for item in contract.get("constraints", [])
            if isinstance(item, dict) and item.get("required") is True
        ],
    }


def build(visible_path: Path, cache_root: Path) -> dict[str, Any]:
    contract, contract_sha, issues = validate_contract(cache_root)
    if issues:
        raise ValueError("；".join(issues))
    visible = json.loads(visible_path.read_text(encoding="utf-8"))
    if not isinstance(visible, dict):
        raise ValueError("VISIBLE_INPUT 必须是对象")
    value = project(visible, contract, contract_sha)
    issues = validate_value(value, contract, contract_sha)
    if issues:
        raise ValueError("；".join(issues))
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("visible_input", type=Path)
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        value = json.dumps(build(args.visible_input, args.cache_root), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(value, encoding="utf-8")
        else:
            print(value, end="")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    print("PASS: visible fields projected to creative brief")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
