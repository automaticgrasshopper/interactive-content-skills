#!/usr/bin/env python3
"""Sole producer-side acceptance command for a formal episode deliverable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from assemble_business_output import BUSINESS_SKILL_VERSION, build_business_output
from completion_gate import validate_handoff, validate_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("business_output", type=Path)
    parser.add_argument("completion_receipt", type=Path)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--expected-endings", type=int, required=True)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    args = parser.parse_args()

    cache_root = args.cache_root.resolve()
    business_path = args.business_output.resolve()
    receipt_path = args.completion_receipt.resolve()
    handoff_path = args.handoff.resolve()
    asset_catalog = cache_root / "asset-catalog.json"
    introductions = cache_root / "character-introductions.json"
    spine = cache_root / "emotional-spine.json"
    issues: list[str] = []
    try:
        actual = json.loads(business_path.read_text(encoding="utf-8"))
        rebuilt, build_issues = build_business_output(
            cache_root,
            asset_catalog,
            introductions,
            spine,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
            None,
            None,
            set(),
            "any",
        )
        issues.extend(build_issues)
        if actual != rebuilt:
            issues.append("业务JSON不是当前完整门禁材料的确定性组装结果")
        issues.extend(validate_receipt(
            receipt_path,
            cache_root,
            business_path,
            asset_catalog,
            introductions,
            spine,
            BUSINESS_SKILL_VERSION,
        ))
        issues.extend(validate_handoff(
            handoff_path,
            cache_root,
            business_path,
            receipt_path,
            BUSINESS_SKILL_VERSION,
        ))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues.append(str(error))

    issues = list(dict.fromkeys(issues))
    if issues:
        print("DELIVERABLE_REJECTED")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("DELIVERABLE_ACCEPTED")
    print("BUSINESS_SCHEMA=passed")
    print("SKILL_ACCEPTANCE=verified")
    print("PROJECT_PROJECTION=not_performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
