#!/usr/bin/env python3
"""Create or verify the sole acceptance receipt for each completed episode."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from build_enhancer_input import build as build_enhancer_input
from dramatization_gate import verify_one as verify_dramatization
from episode_quality_gate import verify_one as verify_quality
from validate_episode import validate_one


VERSION = "nextplay.episode-acceptance.v1"
REQUIRED = {
    "adaptation_source": ("episode-adaptation-sources", ".json"),
    "story_material": ("episode-story-materials", ".json"),
    "writing_input": ("episode-writing-inputs", ".txt"),
    "screenwriter_draft": ("screenplay-drafts", ".md"),
    "screenwriter_receipt": ("screenwriter-receipts", ".json"),
    "enhancer_input": ("enhancer-inputs", ".txt"),
    "enhanced_screenplay": ("enhanced-screenplays", ".md"),
    "formal_episode": ("episodes", ".md"),
    "dramatization_plan": ("dramatization-plans", ".json"),
    "dramatization_receipt": ("dramatization-receipts", ".json"),
    "quality_receipt": ("episode-quality-receipts", ".json"),
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def path_for(cache_root: Path, episode_id: str, spec: tuple[str, str]) -> Path:
    directory, suffix = spec
    return cache_root / directory / f"{episode_id}{suffix}"


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def receipt_path(cache_root: Path, episode_id: str) -> Path:
    return cache_root / "episode-acceptance-receipts" / f"{episode_id}.json"


def build_receipt(cache_root: Path, episode_id: str) -> dict[str, Any]:
    artifacts: dict[str, str] = {}
    paths: dict[str, Path] = {}
    for label, spec in REQUIRED.items():
        path = path_for(cache_root, episode_id, spec)
        if not path.is_file():
            raise ValueError(f"单集验收缺少产物：{episode_id}/{label}")
        paths[label] = path
        artifacts[label] = sha_bytes(path.read_bytes())

    structure_errors = validate_one(cache_root, episode_id)
    dramatization_errors = verify_dramatization(cache_root, episode_id)
    quality_errors = verify_quality(cache_root, episode_id)
    errors = list(dict.fromkeys([*structure_errors, *dramatization_errors, *quality_errors]))
    if errors:
        raise ValueError("单集验收未通过：" + "；".join(errors))

    draft_text = paths["screenwriter_draft"].read_text(encoding="utf-8").strip()
    screenwriter_receipt = json.loads(paths["screenwriter_receipt"].read_text(encoding="utf-8"))
    if screenwriter_receipt.get("status") != "PASS" or screenwriter_receipt.get("draft_sha256") != hashlib.sha256(draft_text.encode("utf-8")).hexdigest():
        raise ValueError(f"原稿回执未绑定当前原稿：{episode_id}")
    material = json.loads(paths["story_material"].read_text(encoding="utf-8"))
    expected_enhancer_input = build_enhancer_input(
        paths["screenwriter_draft"],
        str(material.get("stop_boundary") or ""),
        Path(__file__).resolve().parents[1] / "references" / "vimax-script-enhancer.md",
        Path(__file__).resolve().parents[1] / "references" / "chinese-dialogue-craft.md",
        paths["screenwriter_receipt"],
    )
    if paths["enhancer_input"].read_text(encoding="utf-8").strip() != expected_enhancer_input.strip():
        raise ValueError(f"Enhancer输入不是当前原稿与reference的确定性组装结果：{episode_id}")

    repair_path = cache_root / "review-repair-receipts" / f"{episode_id}.json"
    if repair_path.is_file():
        repair = json.loads(repair_path.read_text(encoding="utf-8"))
        enhanced_sha = hashlib.sha256(paths["enhanced_screenplay"].read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest()
        if repair.get("status") != "PASS" or repair.get("repaired_sha256") != enhanced_sha:
            raise ValueError(f"局部修复回执未绑定当前增强稿：{episode_id}")
        artifacts["local_repair_receipt"] = sha_bytes(repair_path.read_bytes())

    return {
        "contract_version": VERSION,
        "episode_id": episode_id,
        "artifacts": artifacts,
        "checks": {
            "structure": "PASS",
            "dramatization": "PASS",
            "cold_read": "PASS",
        },
        "status": "PASS",
    }


def verify_all(cache_root: Path) -> list[str]:
    synopsis_dir = cache_root / "episode-synopses"
    episode_ids = sorted(path.stem for path in synopsis_dir.glob("episode-*.json"))
    if not episode_ids:
        return ["没有可验收的分集"]
    errors: list[str] = []
    for episode_id in episode_ids:
        path = receipt_path(cache_root, episode_id)
        if not path.is_file():
            errors.append(f"缺少单集验收回执：{episode_id}")
            continue
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
            expected = build_receipt(cache_root, episode_id)
            if actual != expected:
                errors.append(f"单集验收回执已失效：{episode_id}")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(str(error))
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
            print("PASS: all episode acceptance receipts verified")
            return 0
        if not args.episode_id:
            raise ValueError("缺少分集编号")
        receipt = build_receipt(args.cache_root, args.episode_id)
        atomic_write(receipt_path(args.cache_root, args.episode_id), json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: {args.episode_id} accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
