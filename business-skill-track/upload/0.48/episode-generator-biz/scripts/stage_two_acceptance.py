#!/usr/bin/env python3
"""Create once, then cheaply verify, the frozen global planning closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from decision_fissure_gate import verify as verify_fissures
from mainline_story_gate import verify as verify_mainline
from story_treatment_gate import verify as verify_treatment
from synopsis_set_gate import verify as verify_synopsis_set
from validate_emotional_topology import validate_emotional_topology
from validate_mainline_projection import full_issues as validate_mainline_projection
from validate_route_duration import validate as validate_route_duration
from validate_run_basis import validate_basis
from validate_topology_revision import validate_revision


VERSION = "nextplay.episode-stage-two-acceptance.v1"
RECEIPT_NAME = "stage-two-acceptance.json"
REQUIRED_FILES = (
    "run-basis.json",
    "stage-two-input.json",
    "unnumbered-emotional-movement.json",
    "mainline-story-input.json",
    "mainline-story.json",
    "mainline-story-review.json",
    "mainline-decomposition.json",
    "mainline-path.json",
    "decision-fissure-audit.json",
    "decision-fissure-review.json",
    "story-treatment.json",
    "story-treatment-review.json",
    "topology-draft-1.md",
    "topology.md",
    "route-duration.json",
    "emotional-spine.json",
    "synopsis-set-review.json",
    "user-request.md",
    "user-intent-lock.json",
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


def ending_plan(cache_root: Path) -> dict[str, int]:
    basis = json.loads((cache_root / "run-basis.json").read_text(encoding="utf-8"))
    plan = basis.get("ending_plan") or {}
    result = {key: plan.get(key) for key in ("total", "formal", "failure")}
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in result.values()):
        raise ValueError("run-basis ending_plan 不是合法非负整数计划")
    if result["total"] != result["formal"] + result["failure"]:
        raise ValueError("ending_plan.total 必须等于 formal + failure")
    return result


def dependency_paths(cache_root: Path) -> dict[str, Path]:
    result = {name: cache_root / name for name in REQUIRED_FILES}
    synopsis_dir = cache_root / "episode-synopses"
    for path in sorted(synopsis_dir.glob("episode-*.json")):
        result[f"episode-synopses/{path.name}"] = path
    if not any(name.startswith("episode-synopses/") for name in result):
        raise ValueError("阶段二验收缺少全体分集梗概")
    return result


def hashes(cache_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, path in sorted(dependency_paths(cache_root).items()):
        if not path.is_file():
            raise ValueError(f"阶段二验收缺少依赖：{name}")
        result[name] = sha256(path)
    return result


def build(cache_root: Path) -> dict[str, Any]:
    plan = ending_plan(cache_root)
    errors: list[str] = []
    errors.extend(validate_basis(cache_root))
    errors.extend(validate_revision(cache_root / "topology-draft-1.md", cache_root / "topology.md"))
    errors.extend(verify_mainline(cache_root))
    errors.extend(verify_fissures(cache_root))
    errors.extend(verify_treatment(cache_root))
    errors.extend(validate_mainline_projection(cache_root))
    errors.extend(validate_route_duration(
        cache_root / "route-duration.json",
        cache_root / "topology.md",
        cache_root / "stage-two-input.json",
    ))
    errors.extend(verify_synopsis_set(cache_root))
    errors.extend(validate_emotional_topology(
        cache_root / "topology.md",
        cache_root / "emotional-spine.json",
        plan["total"],
        plan["formal"],
        plan["failure"],
    ))
    errors = list(dict.fromkeys(errors))
    if errors:
        raise ValueError("阶段二验收未通过：" + "；".join(errors))
    return {
        "contract_version": VERSION,
        "status": "PASS",
        "ending_plan": plan,
        "files": hashes(cache_root),
    }


def receipt_path(cache_root: Path) -> Path:
    return cache_root / RECEIPT_NAME


def load_verified(cache_root: Path) -> dict[str, Any]:
    path = receipt_path(cache_root)
    if not path.is_file():
        raise ValueError("缺少阶段二验收回执")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("contract_version") != VERSION or receipt.get("status") != "PASS":
        raise ValueError("阶段二验收回执合同或状态错误")
    if receipt.get("ending_plan") != ending_plan(cache_root):
        raise ValueError("阶段二验收回执的结局计划已失效")
    if receipt.get("files") != hashes(cache_root):
        raise ValueError("阶段二冻结材料在验收后发生变化")
    return receipt


def verify(cache_root: Path) -> list[str]:
    try:
        load_verified(cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    return []


def verify_binding(cache_root: Path) -> list[str]:
    """O(1) episode-time check; full dependency hashing is reserved for closure."""
    try:
        path = receipt_path(cache_root)
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("contract_version") != VERSION or receipt.get("status") != "PASS":
            raise ValueError("阶段二验收回执合同或状态错误")
        state_path = cache_root / "run-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("stage_two_receipt_sha256") != sha256(path):
            raise ValueError("运行状态未绑定当前阶段二验收")
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
            print("STAGE_TWO_ACCEPTED")
        else:
            receipt = load_verified(args.cache_root)
            if args.command == "show":
                print(json.dumps(receipt, ensure_ascii=False, indent=2))
            else:
                print("STAGE_TWO_ACCEPTANCE_PASS")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
