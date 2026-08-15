#!/usr/bin/env python3
"""Create or verify hash-only per-episode acceptance receipts."""

from __future__ import annotations

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


VERSION = "nextplay.episode-acceptance.v3"
BASE_ACTIONS = (
    "ADAPT",
    "WRITE_DRAFT",
    "VALIDATE_DRAFT",
    "ENHANCE",
    "VALIDATE_STRUCTURE",
    "PREPARE_REVIEWS",
    "REVIEW_DRAMA",
    "REVIEW_COLD_READ",
)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    return sha_bytes(path.read_bytes())


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
    outcome = str(record.get("outcome") or "PASS")
    files = record.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"运行状态缺少动作产物：{episode_id}/{action}")
    required = expected_outputs(cache_root, action, episode_id, outcome)
    if set(files) != {str(path) for path in required}:
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
    if not isinstance(episode, dict) or episode.get("state") not in {"REVIEWS_PASSED", "EPISODE_ACCEPTED"}:
        raise ValueError(f"单集尚未到达可验收状态：{episode_id}")
    active_actions = set((episode.get("leases") or {}).keys())
    if active_actions - {"ACCEPT_EPISODE"}:
        raise ValueError(f"单集仍有非验收活动租约：{episode_id}/{sorted(active_actions)}")
    outputs = episode.get("outputs") or {}
    actions = list(BASE_ACTIONS)
    if "REPAIR" in outputs or "MERGE_FINDINGS" in outputs:
        actions.extend(("MERGE_FINDINGS", "REPAIR"))
    artifacts: dict[str, str] = {}
    action_outcomes: dict[str, str] = {}
    for action in actions:
        record = outputs.get(action)
        if not isinstance(record, dict):
            raise ValueError(f"单集验收缺少已提交动作：{episode_id}/{action}")
        outcome = str(record.get("outcome") or "PASS")
        if action in {"REVIEW_DRAMA", "REVIEW_COLD_READ"} and outcome != "PASS":
            raise ValueError(f"单集仍有未通过复检：{episode_id}/{action}")
        artifacts.update(verified_action_files(cache_root, episode_id, action, record))
        action_outcomes[action] = outcome
    return {
        "contract_version": VERSION,
        "episode_id": episode_id,
        "episode_dependency_sha256": episode_dependency_sha256(cache_root, episode_id),
        "run_id": state.get("run_id"),
        "action_outcomes": action_outcomes,
        "artifacts": artifacts,
        "status": "PASS",
    }


def verify_one(cache_root: Path, episode_id: str) -> list[str]:
    path = receipt_path(cache_root, episode_id)
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
        expected = build_receipt(cache_root, episode_id)
        return [] if actual == expected else [f"单集验收回执已失效：{episode_id}"]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def verify_all(cache_root: Path) -> list[str]:
    state = load_run_state(cache_root)
    errors: list[str] = []
    for episode_id in state.get("episode_order") or []:
        episode = state["episodes"][episode_id]
        if episode.get("state") != "EPISODE_ACCEPTED":
            errors.append(f"分集状态尚未验收：{episode_id}")
            continue
        path = receipt_path(cache_root, episode_id)
        if not path.is_file():
            errors.append(f"缺少单集验收回执：{episode_id}")
            continue
        recorded = ((episode.get("outputs") or {}).get("ACCEPT_EPISODE") or {}).get("files") or {}
        if recorded.get(str(path.resolve())) != digest(path):
            errors.append(f"状态机未绑定当前单集验收回执：{episode_id}")
    return list(dict.fromkeys(errors))


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
            print("PASS: all episode acceptance receipts verified by hashes")
            return 0
        if not args.episode_id:
            raise ValueError("创建单集验收必须提供episode_id")
        value = build_receipt(args.cache_root, args.episode_id)
        atomic_write(
            receipt_path(args.cache_root, args.episode_id),
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        )
        print(f"EPISODE_ACCEPTED: {args.episode_id}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
