#!/usr/bin/env python3
"""Materialize one compact plan index from an accepted episode route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from episode_plan_index import build_index, validate_index
from screenplay_contract import formal_route_issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("formal_route", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        route = json.loads(args.formal_route.read_text(encoding="utf-8"))
        issues = formal_route_issues(route)
        if issues:
            raise ValueError("；".join(issues))
        value = build_index(route)
        issues = validate_index(route, value)
        if issues:
            raise ValueError("；".join(issues))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"EPISODE_PLAN_INDEX_REJECTED: {error}")
        return 1
    print("EPISODE_PLAN_INDEX_ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
