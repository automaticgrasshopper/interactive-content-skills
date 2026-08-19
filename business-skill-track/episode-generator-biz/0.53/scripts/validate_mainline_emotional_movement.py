#!/usr/bin/env python3
"""Validate story-derived emotional movement before fissures and topology."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from validate_mainline_projection import canonical, decomposition_issues


CONTRACT_VERSION = "nextplay.mainline-emotional-movement.v2"
ROOT_FIELDS = {
    "contract_version", "complete_story_sha256", "decomposition_sha256", "movements",
}
MOVEMENT_FIELDS = {
    "movement_id", "segment_ids", "phase", "source_proof", "current", "target",
    "reality", "pressure", "desired_state", "reality_shift", "control_change",
    "unresolved_task", "catalyst", "audience_known_risk", "candidate_fissures",
}
POINT_FIELDS = {"valence", "arousal", "dominance"}
PHASES = ("setup", "development", "reversal", "resolution")
MIN_DIRECTION = 0.15
MIN_MAJOR_SHIFT = 0.25


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_point(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != POINT_FIELDS:
        raise ValueError(f"{label}必须严格包含valence、arousal、dominance")
    point: dict[str, float] = {}
    for field in POINT_FIELDS:
        item = value.get(field)
        if not isinstance(item, (int, float)) or isinstance(item, bool) or not -1 <= item <= 1:
            raise ValueError(f"{label}/{field}必须是-1到1的数值")
        point[field] = float(item)
    return point


def distance(left: dict[str, float], right: dict[str, float]) -> float:
    return max(abs(left[field] - right[field]) for field in POINT_FIELDS)


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
    reality_points: list[dict[str, float]] = []
    has_major_shift = False
    for index, movement in enumerate(movements, 1):
        if not isinstance(movement, dict) or set(movement) != MOVEMENT_FIELDS:
            raise ValueError(f"主线情绪运动字段错误：第{index}项")
        movement_id = str(movement.get("movement_id") or "")
        segment_ids = movement.get("segment_ids")
        phase = str(movement.get("phase") or "")
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
        if phase not in PHASES:
            raise ValueError(f"主线情绪运动阶段非法：{movement_id}/{phase}")
        current = read_point(movement.get("current"), f"{movement_id}/current")
        target = read_point(movement.get("target"), f"{movement_id}/target")
        reality = read_point(movement.get("reality"), f"{movement_id}/reality")
        if distance(current, target) < MIN_DIRECTION:
            raise ValueError(f"主线情绪运动缺少真实欲望方向：{movement_id}")
        if distance(target, reality) < MIN_DIRECTION:
            raise ValueError(f"主线情绪运动缺少目标与现实反差：{movement_id}")
        if reality_points and distance(reality_points[-1], reality) >= MIN_MAJOR_SHIFT:
            has_major_shift = True
        reality_points.append(reality)
        for field in (
            "pressure", "desired_state", "reality_shift", "control_change", "unresolved_task",
            "catalyst", "audience_known_risk",
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
    if len(reality_points) > 1 and not has_major_shift:
        raise ValueError("主线情绪运动没有任何足以改变路线判断的真实位移")
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
        return not_accepted(__file__)
    print("PASS: mainline emotional movement is story-derived and pre-topology")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
