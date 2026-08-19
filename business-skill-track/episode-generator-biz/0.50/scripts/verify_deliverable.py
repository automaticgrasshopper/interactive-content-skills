#!/usr/bin/env python3
"""Sole producer-side acceptance command for a formal episode deliverable."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from assemble_business_output import BUSINESS_SKILL_VERSION, assemble_snapshot, resolve_ending_counts
from completion_gate import validate_handoff, validate_receipt
from validate_business_output import validate as validate_business_output

ACCEPTANCE_VERSION = "nextplay.delivery-accepted.v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("business_output", type=Path)
    parser.add_argument("completion_receipt", type=Path)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--expected-major-endings", type=int)
    parser.add_argument("--acceptance-receipt", type=Path)
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
        expected_major_endings = resolve_ending_counts(cache_root, args.expected_major_endings)
        actual = json.loads(business_path.read_text(encoding="utf-8"))
        rebuilt = assemble_snapshot(cache_root)
        if actual != rebuilt:
            issues.append("业务JSON不是当前完整门禁材料的确定性组装结果")
        issues.extend(validate_business_output(
            actual,
            asset_catalog,
            expected_major_endings,
            None,
            set(),
            "any",
        ))
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
    acceptance_path = args.acceptance_receipt or cache_root / "delivery-accepted.json"
    acceptance = {
        "contract_version": ACCEPTANCE_VERSION,
        "business_output_sha256": hashlib.sha256(business_path.read_bytes()).hexdigest(),
        "completion_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "handoff_sha256": hashlib.sha256(handoff_path.read_bytes()).hexdigest(),
        "status": "PASS",
    }
    acceptance_path.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DELIVERABLE_ACCEPTED")
    print("BUSINESS_SCHEMA=passed")
    print("SKILL_ACCEPTANCE=verified")
    print("PROJECT_PROJECTION=not_performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
