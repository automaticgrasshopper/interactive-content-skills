#!/usr/bin/env python3
"""Validate the pre-topology emotional movement and private path envelope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "nextplay.unnumbered-emotional-movement.v1"
ROOT_FIELDS = {"contract_version", "scale", "phases"}
SCALE_FIELDS = {
    "minimum_legal_path_length",
    "target_formal_path_length_min",
    "target_formal_path_length_max",
    "interaction_min",
    "interaction_max",
    "source",
}
PHASE_FIELDS = {
    "phase",
    "current",
    "target",
    "reality",
    "catalyst",
    "audience_known_risk",
    "candidate_fissures",
}
COORDINATE_FIELDS = {"v", "a", "d"}


def validate_coordinate(value: Any, label: str, issues: list[str]) -> None:
    if not isinstance(value, dict) or set(value) != COORDINATE_FIELDS:
        issues.append(f"{label}必须只含v/a/d")
        return
    for axis in ("v", "a", "d"):
        number = value.get(axis)
        if (
            not isinstance(number, (int, float))
            or isinstance(number, bool)
            or number < -1
            or number > 1
        ):
            issues.append(f"{label}.{axis}必须是[-1,1]数值")


def validate(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"未编号情绪运动不可用：{error}"]
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        return ["未编号情绪运动根字段错误"]
    if data.get("contract_version") != CONTRACT_VERSION:
        issues.append(f"合同版本错误：期望{CONTRACT_VERSION}")

    scale = data.get("scale")
    if not isinstance(scale, dict) or set(scale) != SCALE_FIELDS:
        issues.append("scale字段错误")
    else:
        values: dict[str, int] = {}
        for field in (
            "minimum_legal_path_length",
            "target_formal_path_length_min",
            "target_formal_path_length_max",
            "interaction_min",
            "interaction_max",
        ):
            value = scale.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                issues.append(f"scale.{field}必须是正整数")
            else:
                values[field] = value
        if values.get("minimum_legal_path_length") != 2:
            issues.append("所有结局的合法最短路径必须固定为2")
        if values.get("target_formal_path_length_min", 0) > values.get("target_formal_path_length_max", 0):
            issues.append("正式结局路线目标区间倒置")
        if values.get("target_formal_path_length_min", 0) < values.get("minimum_legal_path_length", 0):
            issues.append("正式结局路线目标下限不得短于合法最短路径")
        if values.get("interaction_min", 0) > values.get("interaction_max", 0):
            issues.append("互动探索区间倒置")
        if values.get("interaction_max", 0) > values.get("target_formal_path_length_max", 0):
            issues.append("互动上限不得超过正式结局路线目标上限")
        if scale.get("source") != "duration-and-causal-capacity":
            issues.append("scale.source必须是duration-and-causal-capacity")

    phases = data.get("phases")
    if not isinstance(phases, list) or len(phases) != 4:
        issues.append("phases必须依次包含起承转合四段")
        return issues
    actual_phases: list[str] = []
    fissure_count = 0
    for index, phase in enumerate(phases, 1):
        if not isinstance(phase, dict) or set(phase) != PHASE_FIELDS:
            issues.append(f"第{index}段字段错误")
            continue
        actual_phases.append(str(phase.get("phase") or ""))
        for coordinate in ("current", "target", "reality"):
            validate_coordinate(phase.get(coordinate), f"第{index}段.{coordinate}", issues)
        for field in ("catalyst", "audience_known_risk"):
            if len(str(phase.get(field) or "").strip()) < 8:
                issues.append(f"第{index}段.{field}过短")
        fissures = phase.get("candidate_fissures")
        if not isinstance(fissures, list) or any(
            not isinstance(item, str) or len(item.strip()) < 8 for item in fissures
        ):
            issues.append(f"第{index}段.candidate_fissures必须是可读字符串数组")
        else:
            fissure_count += len(fissures)
    if actual_phases != ["起", "承", "转", "合"]:
        issues.append(f"阶段顺序错误：{actual_phases}")
    if isinstance(scale, dict):
        minimum = scale.get("interaction_min")
        if isinstance(minimum, int) and fissure_count < minimum:
            issues.append("候选裂缝数量少于互动探索下限")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("movement", type=Path)
    args = parser.parse_args()
    issues = validate(args.movement)
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: unnumbered emotional movement and private path envelope are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
