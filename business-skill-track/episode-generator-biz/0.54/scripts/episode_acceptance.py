#!/usr/bin/env python3
"""Create or verify hash-only per-episode acceptance receipts."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from action_contracts import expected_outputs
from dependency_binding import episode_dependency_sha256
from run_state import load as load_run_state

VERSION = "nextplay.episode-acceptance.v7"
ACTIONS = ("ADAPT", "WRITE_EPISODE", "VALIDATE_STRUCTURE", "REVIEW_EPISODE")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def receipt_path(cache_root: Path, episode_id: str) -> Path:
    return cache_root / "episode-acceptance-receipts" / f"{episode_id}.json"


def verified_action_files(cache_root: Path, episode_id: str, action: str, record: dict[str, Any]) -> dict[str, str]:
    if record.get("outcome") != "PASS":
        raise ValueError(f"动作未通过：{episode_id}/{action}")
    files = record.get("files")
    required = expected_outputs(cache_root, action, episode_id)
    if not isinstance(files, dict) or set(files) != {str(path) for path in required}:
        raise ValueError(f"运行状态动作产物集合错误：{episode_id}/{action}")
    verified: dict[str, str] = {}
    for path in required:
        if not path.is_file() or files.get(str(path)) != digest(path):
            raise ValueError(f"原子动作产物已失效：{episode_id}/{action}/{path.name}")
        verified[str(path.relative_to(cache_root.resolve()))] = digest(path)
    return verified


def build_receipt(cache_root: Path, episode_id: str) -> dict[str, Any]:
    state = load_run_state(cache_root)
    episode = (state.get("episodes") or {}).get(episode_id)
    if not isinstance(episode, dict) or episode.get("state") not in {"QUALITY_REVIEWED", "EPISODE_ACCEPTED"}:
        raise ValueError(f"单集尚未完成独立质量复检：{episode_id}")
    if set((episode.get("leases") or {})) - {"ACCEPT_EPISODE"}:
        raise ValueError(f"单集仍有非验收活动租约：{episode_id}")
    outputs = episode.get("outputs") or {}
    artifacts: dict[str, str] = {}
    for action in ACTIONS:
        record = outputs.get(action)
        if not isinstance(record, dict):
            raise ValueError(f"单集验收缺少动作：{episode_id}/{action}")
        artifacts.update(verified_action_files(cache_root, episode_id, action, record))
    return {
        "contract_version": VERSION,
        "episode_id": episode_id,
        "episode_dependency_sha256": episode_dependency_sha256(cache_root, episode_id),
        "run_id": state.get("run_id"),
        "action_outcomes": {action: "PASS" for action in ACTIONS},
        "artifacts": artifacts,
        "status": "PASS",
    }


def verify_all(cache_root: Path) -> list[str]:
    state = load_run_state(cache_root)
    errors: list[str] = []
    for episode_id in state.get("episode_order") or []:
        episode = state["episodes"][episode_id]
        path = receipt_path(cache_root, episode_id)
        if episode.get("state") != "EPISODE_ACCEPTED":
            errors.append(f"分集状态尚未验收：{episode_id}")
        elif not path.is_file():
            errors.append(f"缺少单集验收回执：{episode_id}")
        else:
            recorded = ((episode.get("outputs") or {}).get("ACCEPT_EPISODE") or {}).get("files") or {}
            if recorded.get(str(path.resolve())) != digest(path):
                errors.append(f"状态机未绑定当前单集验收回执：{episode_id}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("episode_id", nargs="?")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    try:
        if args.all:
            errors = verify_all(args.cache_root)
            if errors:
                raise ValueError("；".join(errors))
        else:
            if not args.episode_id:
                raise ValueError("缺少episode_id")
            atomic_write(receipt_path(args.cache_root, args.episode_id), json.dumps(build_receipt(args.cache_root, args.episode_id), ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    print("PASS")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
