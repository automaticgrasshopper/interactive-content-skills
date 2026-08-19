#!/usr/bin/env python3
"""Freeze and verify the complete story-to-synopsis planning closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from complete_story_gate import verify as verify_complete_story
from decision_fissure_gate import verify as verify_fissures
from story_treatment_gate import verify as verify_treatment
from synopsis_set_gate import verify as verify_synopsis_set
from validate_creative_brief import validate_frozen as validate_creative_brief
from validate_emotional_topology import validate_emotional_topology
from validate_mainline_projection import full_issues as validate_mainline_projection
from validate_route_duration import validate as validate_route_duration
from validate_topology_revision import validate_revision
from topology_dual_review_gate import verify as verify_topology_reviews


VERSION = "nextplay.episode-planning-acceptance.v2"
RECEIPT_NAME = "planning-acceptance.json"
REQUIRED_FILES = (
    "user-request.md", "user-intent-lock.json", "creative-brief.json",
    "complete-story.json", "complete-story-review.json",
    "mainline-decomposition.json", "mainline-path.json", "mainline-projection-review.json",
    "decision-fissure-audit.json", "decision-fissure-review.json",
    "story-treatment.json", "story-treatment-review.json",
    "topology-draft-1.md", "topology.md", "route-duration.json",
    "topology-review-a.json", "topology-review-b.json",
    "emotional-spine.json", "synopsis-set-review.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def resolved_endings(cache_root: Path) -> dict[str, int]:
    treatment = json.loads((cache_root / "story-treatment.json").read_text(encoding="utf-8"))
    endings = treatment.get("endings") if isinstance(treatment, dict) else None
    if not isinstance(endings, list) or not endings:
        raise ValueError("支线故事图没有自然形成主要结局")
    counts = {
        kind: sum(1 for item in endings if isinstance(item, dict) and item.get("kind") == kind)
        for kind in ("main", "expected", "failure")
    }
    small = treatment.get("small_endings")
    if sum(counts.values()) != len(endings) or not isinstance(small, list):
        raise ValueError("支线故事图存在非法主要结局类型")
    if counts["main"] != 1 or counts["expected"] < 1 or counts["failure"] < 1 or len(small) < 1:
        raise ValueError("支线故事图必须有且仅有一个主结局，并至少各有一个期望结局、失败结局和小结局")
    return {"major": len(endings), **counts, "small": len(small)}


def dependency_paths(cache_root: Path) -> dict[str, Path]:
    result = {name: cache_root / name for name in REQUIRED_FILES}
    for path in sorted((cache_root / "episode-synopses").glob("episode-*.json")):
        result[f"episode-synopses/{path.name}"] = path
    if not any(name.startswith("episode-synopses/") for name in result):
        raise ValueError("规划验收缺少全体分集梗概")
    return result


def hashes(cache_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, path in sorted(dependency_paths(cache_root).items()):
        if not path.is_file():
            raise ValueError(f"规划验收缺少依赖：{name}")
        result[name] = sha256(path)
    return result


def content_leaves(cache_root: Path) -> dict[str, Any]:
    global_names = (
        "user-request.md", "user-intent-lock.json", "creative-brief.json",
        "complete-story.json", "mainline-decomposition.json", "mainline-path.json",
        "story-treatment.json", "topology.md", "route-duration.json", "emotional-spine.json",
    )
    global_hashes = {name: sha256(cache_root / name) for name in global_names}
    episodes = {}
    for path in sorted((cache_root / "episode-synopses").glob("episode-*.json")):
        episodes[path.stem] = sha256(path)
    payload = {"global": global_hashes, "episodes": episodes}
    return {
        **payload,
        "content_sha256": hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
    }


def build(cache_root: Path) -> dict[str, Any]:
    validate_creative_brief(cache_root)
    endings = resolved_endings(cache_root)
    errors: list[str] = []
    errors.extend(verify_complete_story(cache_root))
    errors.extend(verify_fissures(cache_root))
    errors.extend(verify_treatment(cache_root))
    errors.extend(validate_revision(cache_root / "topology-draft-1.md", cache_root / "topology.md"))
    errors.extend(validate_mainline_projection(cache_root))
    errors.extend(validate_route_duration(cache_root / "route-duration.json", cache_root / "topology.md"))
    errors.extend(verify_topology_reviews(cache_root))
    errors.extend(verify_synopsis_set(cache_root))
    errors.extend(validate_emotional_topology(
        cache_root / "topology.md", cache_root / "emotional-spine.json",
        endings["major"], endings["main"], endings["expected"], endings["failure"], endings["small"],
    ))
    errors = list(dict.fromkeys(errors))
    if errors:
        raise ValueError("规划验收未通过：" + "；".join(errors))
    return {
        "contract_version": VERSION,
        "status": "PASS",
        "resolved_endings": endings,
        "files": hashes(cache_root),
        "content_leaves": content_leaves(cache_root),
    }


def receipt_path(cache_root: Path) -> Path:
    return cache_root / RECEIPT_NAME


def load_verified(cache_root: Path) -> dict[str, Any]:
    path = receipt_path(cache_root)
    if not path.is_file():
        raise ValueError("缺少规划验收回执")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("contract_version") != VERSION or receipt.get("status") != "PASS":
        raise ValueError("规划验收回执合同或状态错误")
    if receipt.get("resolved_endings") != resolved_endings(cache_root):
        raise ValueError("规划验收回执的实际结局统计已失效")
    if receipt.get("files") != hashes(cache_root) or receipt.get("content_leaves") != content_leaves(cache_root):
        raise ValueError("规划冻结材料在验收后发生变化")
    return receipt


def verify(cache_root: Path) -> list[str]:
    try:
        load_verified(cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    return []


def verify_binding(cache_root: Path) -> list[str]:
    try:
        receipt = json.loads(receipt_path(cache_root).read_text(encoding="utf-8"))
        state = json.loads((cache_root / "run-state.json").read_text(encoding="utf-8"))
        current = str((receipt.get("content_leaves") or {}).get("content_sha256") or "")
        if state.get("planning_content_sha256") != current:
            raise ValueError("运行状态未绑定当前规划内容")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("create", "verify", "show"))
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "create":
            receipt = build(args.cache_root)
            atomic_write(receipt_path(args.cache_root), receipt)
            print("PLANNING_ACCEPTED")
        else:
            receipt = load_verified(args.cache_root)
            if args.command == "show":
                print(json.dumps(receipt, ensure_ascii=False, indent=2))
            else:
                print("PLANNING_ACCEPTANCE_PASS")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
