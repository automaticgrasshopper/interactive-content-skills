#!/usr/bin/env python3
"""Create and verify immutable handoffs between the split episode skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


CONTRACT_VERSION = "nextplay.episode-split-handoff.v1"

PLANNING_FILES = (
    "user-request.md",
    "user-intent-lock.json",
    "run-basis.json",
    "asset-catalog.json",
    "stage-two-input.json",
    "unnumbered-emotional-movement.json",
    "mainline-story-input.json",
    "mainline-story.json",
    "mainline-story-review.json",
    "mainline-decomposition.json",
    "decision-fissure-audit.json",
    "decision-fissure-review.json",
    "story-treatment.json",
    "story-treatment-review.json",
    "topology-draft-1.md",
    "topology.md",
    "mainline-path.json",
    "route-duration.json",
    "emotional-spine.json",
    "synopsis-set-review.json",
)

WRITING_PATTERNS = (
    "episode-adaptation-sources/{episode_id}.json",
    "episode-story-materials/{episode_id}.json",
    "episode-writing-inputs/{episode_id}.txt",
    "screenplay-drafts/{episode_id}.md",
    "screenwriter-receipts/{episode_id}.json",
)


class HandoffError(ValueError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffError(f"无法读取合法JSON：{path}") from exc


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def rooted_path(root: Path, name: str) -> Path:
    normalized_root = root.resolve()
    candidate = (normalized_root / name).resolve()
    try:
        candidate.relative_to(normalized_root)
    except ValueError as exc:
        raise HandoffError(f"交接路径越过缓存目录：{name}") from exc
    return candidate


def require_files(root: Path, names: Iterable[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in names:
        path = rooted_path(root, name)
        if not path.is_file() or path.stat().st_size == 0:
            raise HandoffError(f"缺少非空阶段产物：{name}")
        hashes[name] = sha256(path)
    return hashes


def episode_ids(root: Path) -> list[str]:
    synopsis_dir = root / "episode-synopses"
    ids = sorted(path.stem for path in synopsis_dir.glob("episode-*.json"))
    if not ids:
        raise HandoffError("没有冻结分集梗概")
    expected = [f"episode-{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise HandoffError("分集梗概编号不连续")
    return ids


def require_clean_review(root: Path, name: str) -> None:
    data = load_json(root / name)
    if not isinstance(data, dict):
        raise HandoffError(f"复检结果不是对象：{name}")
    issues = data.get("issues")
    if issues not in (None, []):
        raise HandoffError(f"复检仍有未解决问题：{name}")


def verify_manifest(root: Path, payload: dict[str, Any], expected_stage: str) -> None:
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise HandoffError("交接合同版本不匹配")
    if payload.get("stage") != expected_stage:
        raise HandoffError("交接阶段不匹配")
    expected_status = "PLANNING_ACCEPTED" if expected_stage == "planning" else "WRITING_ACCEPTED"
    if payload.get("status") != expected_status:
        raise HandoffError("交接状态未放行")
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise HandoffError("交接文件清单为空")
    for name, expected_hash in files.items():
        if not isinstance(name, str) or not isinstance(expected_hash, str):
            raise HandoffError("交接文件清单非法")
        path = rooted_path(root, name)
        if not path.is_file() or sha256(path) != expected_hash:
            raise HandoffError(f"交接后文件已缺失或变化：{name}")


def create_planning(root: Path, output: Path) -> None:
    hashes = require_files(root, PLANNING_FILES)
    for review in (
        "mainline-story-review.json",
        "decision-fissure-review.json",
        "story-treatment-review.json",
        "synopsis-set-review.json",
    ):
        require_clean_review(root, review)
    ids = episode_ids(root)
    synopsis_names = [f"episode-synopses/{episode_id}.json" for episode_id in ids]
    hashes.update(require_files(root, synopsis_names))
    payload = {
        "contract_version": CONTRACT_VERSION,
        "stage": "planning",
        "status": "PLANNING_ACCEPTED",
        "producer": "episode-branch-planner-biz",
        "next_skill": "episode-screenwriter-biz",
        "episode_ids": ids,
        "files": dict(sorted(hashes.items())),
    }
    atomic_write(output, payload)
    print("PLANNING_ACCEPTED")


def verify_planning(root: Path, handoff: Path) -> dict[str, Any]:
    payload = load_json(handoff)
    if not isinstance(payload, dict):
        raise HandoffError("规划交接不是对象")
    verify_manifest(root, payload, "planning")
    if payload.get("episode_ids") != episode_ids(root):
        raise HandoffError("规划交接的分集集合已变化")
    print("PLANNING_HANDOFF_PASS")
    return payload


def create_writing(root: Path, planning_handoff: Path, output: Path) -> None:
    planning = verify_planning(root, planning_handoff)
    ids = planning["episode_ids"]
    names = [pattern.format(episode_id=episode_id) for episode_id in ids for pattern in WRITING_PATTERNS]
    hashes = require_files(root, names)
    for episode_id in ids:
        receipt = load_json(root / f"screenwriter-receipts/{episode_id}.json")
        if not isinstance(receipt, dict) or receipt.get("episode_id") != episode_id or receipt.get("status") != "PASS":
            raise HandoffError(f"Screenwriter原稿未通过：{episode_id}")
        draft = root / f"screenplay-drafts/{episode_id}.md"
        if receipt.get("draft_sha256") != sha256(draft):
            raise HandoffError(f"Screenwriter回执与原稿不一致：{episode_id}")
    hashes[planning_handoff.relative_to(root).as_posix()] = sha256(planning_handoff)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "stage": "writing",
        "status": "WRITING_ACCEPTED",
        "producer": "episode-screenwriter-biz",
        "next_skill": "episode-script-validator-biz",
        "planning_handoff_sha256": sha256(planning_handoff),
        "episode_ids": ids,
        "files": dict(sorted(hashes.items())),
    }
    atomic_write(output, payload)
    print("WRITING_ACCEPTED")


def verify_writing(root: Path, planning_handoff: Path, writing_handoff: Path) -> None:
    planning = verify_planning(root, planning_handoff)
    payload = load_json(writing_handoff)
    if not isinstance(payload, dict):
        raise HandoffError("写作交接不是对象")
    verify_manifest(root, payload, "writing")
    if payload.get("episode_ids") != planning.get("episode_ids"):
        raise HandoffError("写作交接的分集集合与规划不一致")
    if payload.get("planning_handoff_sha256") != sha256(planning_handoff):
        raise HandoffError("写作交接未绑定当前规划交接")
    print("WRITING_HANDOFF_PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("planning-create", "planning-verify", "writing-create", "writing-verify"):
        sub = subparsers.add_parser(command)
        sub.add_argument("root", type=Path)
        if command in ("planning-verify", "writing-create", "writing-verify"):
            sub.add_argument("--planning-handoff", type=Path, required=True)
        if command == "writing-verify":
            sub.add_argument("--writing-handoff", type=Path, required=True)
        if command in ("planning-create", "writing-create"):
            sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == "planning-create":
            create_planning(root, args.output.resolve())
        elif args.command == "planning-verify":
            verify_planning(root, args.planning_handoff.resolve())
        elif args.command == "writing-create":
            create_writing(root, args.planning_handoff.resolve(), args.output.resolve())
        else:
            verify_writing(root, args.planning_handoff.resolve(), args.writing_handoff.resolve())
    except HandoffError as exc:
        print(f"HANDOFF_FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
