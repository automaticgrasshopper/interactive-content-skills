#!/usr/bin/env python3
"""Atomically accept one node screenplay; never writes or replaces the route."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from screenplay_contract import seal


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
    parser.add_argument("formal_route", type=Path)
    parser.add_argument("node_draft", type=Path)
    parser.add_argument("node_patch", type=Path)
    parser.add_argument("--accepted-at")
    args = parser.parse_args()
    try:
        route = json.loads(args.formal_route.read_text(encoding="utf-8"))
        draft = json.loads(args.node_draft.read_text(encoding="utf-8"))
        accepted = seal(route, draft, args.accepted_at)
        atomic_json(args.node_patch, accepted)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"NODE_SCREENPLAY_REJECTED: {error}")
        return 1
    print("NODE_SCREENPLAY_ACCEPTED")
    print(f"NODE_ID={accepted['node_id']}")
    print(f"SCREENPLAY_HASH={accepted['screenplay_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
