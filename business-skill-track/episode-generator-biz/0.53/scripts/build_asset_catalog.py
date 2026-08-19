#!/usr/bin/env python3
"""Derive the lightweight validation catalog from the frozen creative brief."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import json
from pathlib import Path

from validate_creative_brief import validate_frozen

VERSION = "nextplay.episode-assets.v1"


def build(cache_root: Path) -> dict[str, object]:
    brief = validate_frozen(cache_root)
    assets = brief.get("assets") or {}
    names = {key: [str(item["name"]).strip() for item in assets.get(key) or []] for key in ("characters", "scenes", "props")}
    return {"contract_version": VERSION, **names, "optional_characters": [], "character_aliases": {name: [] for name in names["characters"]}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = args.output or args.cache_root / "asset-catalog.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(build(args.cache_root), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    print("ASSET_CATALOG_READY")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
