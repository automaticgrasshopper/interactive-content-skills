#!/usr/bin/env python3
"""Build the sole frozen input packet for one node."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from screenplay_contract import formal_route_issues
from stage_contract import build_packet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("formal_route", type=Path)
    parser.add_argument("node_context", type=Path)
    parser.add_argument("node_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        route = json.loads(args.formal_route.read_text(encoding="utf-8"))
        context = json.loads(args.node_context.read_text(encoding="utf-8"))
        issues = formal_route_issues(route)
        if issues:
            raise ValueError("；".join(issues))
        value = build_packet(route, context, args.node_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"NODE_WRITING_PACKET_REJECTED: {error}")
        return 1
    print("NODE_WRITING_PACKET_ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
