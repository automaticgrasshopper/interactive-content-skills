#!/usr/bin/env python3
"""Validate story-derived emotional movement before fissures and topology."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from validate_mainline_projection import canonical, decomposition_issues


CONTRACT_VERSION = "nextplay.mainline-emotional-movement.v1"
ROOT_FIELDS = {
    "contract_version", "complete_story_sha256", "decomposition_sha256", "movements",
}
MOVEMENT_FIELDS = {
    "movement_id", "segment_ids", "source_proof", "pressure", "desired_state",
    "reality_shift", "control_change", "unresolved_task", "candidate_fissures",
}


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_movement(cache_root: Path) -> tuple[Path, dict[str, Any]]:
    issues, complete_story, decomposition = decomposition_issues(cache_root)
    if issues:
        raise ValueError("主线分解未通过：" + "；".join(issues))
    path = cache_root / "mainline-emotional-movement.json"
    if not path.is_file():
        raise ValueError("缺少主线情绪运动：mainline-emotional-movement.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        raise ValueError("主线情绪运动根字段错误")
    if data.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(f"主线情绪运动合同错误：期望 {CONTRACT_VERSION}")
    if data.get("complete_story_sha256") != digest(complete_story):
        raise ValueError("主线情绪运动未绑定当前完整故事")
    if data.get("decomposition_sha256") != digest(decomposition):
        raise ValueError("主线情绪运动未绑定当前主线分解")

    segments = decomposition["segments"]
    source_by_id = {str(item["segment_id"]): str(item["source_text"]) for item in segments}
    movements = data.get("movements")
    if not isinstance(movements, list) or not movements:
        raise ValueError("主线情绪运动必须包含至少一段真实运动")
    movement_ids: set[str] = set()
    covered_segments: set[str] = set()
    for index, movement in enumerate(movements, 1):
        if not isinstance(movement, dict) or set(movement) != MOVEMENT_FIELDS:
            raise ValueError(f"主线情绪运动字段错误：第{index}项")
        movement_id = str(movement.get("movement_id") or "")
        segment_ids = movement.get("segment_ids")
        proof = str(movement.get("source_proof") or "").strip()
        if not movement_id.startswith("movement-") or movement_id in movement_ids:
            raise ValueError(f"主线情绪运动编号非法或重复：{movement_id}")
        if not isinstance(segment_ids, list) or not segment_ids or any(
            not isinstance(item, str) or item not in source_by_id for item in segment_ids
        ):
            raise ValueError(f"主线情绪运动引用了非法切片：{movement_id}")
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError(f"主线情绪运动重复引用切片：{movement_id}")
        corpus = "\n".join(source_by_id[item] for item in segment_ids)
        if len(proof) < 8 or proof not in corpus:
            raise ValueError(f"主线情绪运动缺少切片内逐字证据：{movement_id}")
        for field in (
            "pressure", "desired_state", "reality_shift", "control_change", "unresolved_task",
        ):
            if len(str(movement.get(field) or "").strip()) < 6:
                raise ValueError(f"主线情绪运动缺少{field}：{movement_id}")
        fissures = movement.get("candidate_fissures")
        if not isinstance(fissures, list) or any(
            not isinstance(item, str) or len(item.strip()) < 4 for item in fissures
        ):
            raise ValueError(f"主线情绪运动候选裂缝字段错误：{movement_id}")
        movement_ids.add(movement_id)
        covered_segments.update(segment_ids)
    missing = [segment_id for segment_id in source_by_id if segment_id not in covered_segments]
    if missing:
        raise ValueError(f"主线情绪运动未覆盖全部主线切片：{missing}")
    return path, data


def validate(cache_root: Path) -> list[str]:
    try:
        read_movement(cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    issues = validate(args.cache_root)
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: mainline emotional movement is story-derived and pre-topology")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
