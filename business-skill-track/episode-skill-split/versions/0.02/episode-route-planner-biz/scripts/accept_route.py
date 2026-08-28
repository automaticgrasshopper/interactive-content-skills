#!/usr/bin/env python3
"""Atomically save a validated route without requiring screenplay artifacts."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from planning_gate import verify_root
from route_contract import seal


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--accepted-at")
    args = parser.parse_args()
    try:
        candidate = json.loads((args.cache_root / "route-candidate.json").read_text(encoding="utf-8"))
        planning_issues = verify_root(args.cache_root)
        if planning_issues:
            raise ValueError("规划验收未通过：" + "；".join(planning_issues))
        accepted = seal(candidate, args.accepted_at)
        atomic_json(args.output, accepted)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ROUTE_REJECTED: {error}")
        return 1
    print("ROUTE_ACCEPTED")
    print(f"ROUTE_OUTPUT_HASH={accepted['route_output_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
