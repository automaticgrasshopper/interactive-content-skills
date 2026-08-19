#!/usr/bin/env python3
"""Seal one deterministic structure result so Acceptance never replays it."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from validate_episode import validate_one
from dependency_binding import episode_dependency_sha256


VERSION = "nextplay.episode-structure-receipt.v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def seal(cache_root: Path, episode_id: str) -> dict[str, object]:
    errors = validate_one(cache_root, episode_id)
    if errors:
        raise ValueError("；".join(errors))
    formal = cache_root / "episodes" / f"{episode_id}.md"
    screenplay = cache_root / "screenplays" / f"{episode_id}.md"
    return {
        "contract_version": VERSION,
        "episode_id": episode_id,
        "formal_episode_sha256": digest(formal),
        "screenplay_sha256": digest(screenplay),
        "episode_dependency_sha256": episode_dependency_sha256(cache_root, episode_id),
        "status": "PASS",
    }


def verify(cache_root: Path, episode_id: str) -> list[str]:
    path = cache_root / "episode-structure-receipts" / f"{episode_id}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        formal = cache_root / "episodes" / f"{episode_id}.md"
        screenplay = cache_root / "screenplays" / f"{episode_id}.md"
        expected = {
            "contract_version": VERSION,
            "episode_id": episode_id,
            "formal_episode_sha256": digest(formal),
            "screenplay_sha256": digest(screenplay),
            "episode_dependency_sha256": episode_dependency_sha256(cache_root, episode_id),
            "status": "PASS",
        }
        return [] if value == expected else [f"结构回执已失效：{episode_id}"]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seal", "verify"))
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("episode_id")
    args = parser.parse_args()
    try:
        if args.command == "seal":
            value = seal(args.cache_root, args.episode_id)
            atomic_write(
                args.cache_root / "episode-structure-receipts" / f"{args.episode_id}.json",
                value,
            )
            from episode_quality_gate import write_packet
            write_packet(args.cache_root, args.episode_id)
        else:
            errors = verify(args.cache_root, args.episode_id)
            if errors:
                raise ValueError("；".join(errors))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    print(f"PASS: {args.command} {args.episode_id}")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
