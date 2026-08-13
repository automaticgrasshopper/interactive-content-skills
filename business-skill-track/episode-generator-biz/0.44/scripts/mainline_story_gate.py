#!/usr/bin/env python3
"""Freeze and independently review the pre-topology linear mainline story."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from build_stage_two_input import validate_frozen as validate_stage_two_input
from validate_emotional_movement import validate as validate_emotional_movement


CONTRACT_VERSION = "nextplay.episode-mainline-story.v1"
RECEIPT_VERSION = "nextplay.episode-mainline-story-review.v1"
ROOT_FIELDS = {"contract_version", "title", "complete_story", "expected_ending_title"}
COMPREHENSION_FIELDS = {
    "protagonist_goal": "主角目标",
    "causal_progression": "连续因果",
    "required_events": "必保事件",
    "expected_ending": "期待性正式结局",
}
REQUIRED_CHECKS = ["上游事实", "人物动机与知情边界", "连续因果", "关键真相", "必保事件", "期待性类型兑现"]
BRANCH_MARKERS = ("如果", "或者", "另一条路线", "另一种路线", "玩家可以", "选择A", "选择B", "选项A", "选项B")
EPISODE_ID = re.compile(r"episode-\d{3}")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_mainline(cache_root: Path) -> tuple[Path, dict[str, Any]]:
    path = cache_root / "mainline-story.json"
    if not path.is_file():
        raise ValueError("缺少冻结主线：mainline-story.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        raise ValueError("冻结主线根字段错误")
    if data.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(f"冻结主线合同错误：期望 {CONTRACT_VERSION}")
    story = str(data.get("complete_story") or "").strip()
    if len(str(data.get("title") or "").strip()) < 2 or len(story) < 500:
        raise ValueError("冻结主线缺少标题或完整故事过短")
    if len(str(data.get("expected_ending_title") or "").strip()) < 2:
        raise ValueError("冻结主线缺少期待性正式结局标题")
    found = [marker for marker in BRANCH_MARKERS if marker in story]
    if found:
        raise ValueError("冻结主线含条件或分支可能性语言：" + "、".join(found))
    if EPISODE_ID.search(story):
        raise ValueError("冻结主线不得提前出现分集编号")
    return path, data


def packet(cache_root: Path) -> dict[str, Any]:
    path, mainline = read_mainline(cache_root)
    stage_two = validate_stage_two_input(cache_root)
    movement_path = cache_root / "unnumbered-emotional-movement.json"
    movement_issues = validate_emotional_movement(movement_path)
    if movement_issues:
        raise ValueError("未编号情绪运动未通过：" + "；".join(movement_issues))
    return {
        "packet_version": RECEIPT_VERSION,
        "mainline_path": str(path),
        "mainline_sha256": digest(mainline),
        "stage_two_input_sha256": digest(stage_two),
        "required_comprehension": COMPREHENSION_FIELDS,
        "required_checks": REQUIRED_CHECKS,
        "mainline": mainline,
    }


def validate_review(packet_value: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    story = packet_value["mainline"]["complete_story"]
    comprehension = review.get("comprehension") if isinstance(review.get("comprehension"), dict) else {}
    for key, label in COMPREHENSION_FIELDS.items():
        item = comprehension.get(key) if isinstance(comprehension.get(key), dict) else {}
        answer = str(item.get("answer") or "").strip()
        proof = str(item.get("proof") or "").strip()
        if len(answer) < 8 or len(proof) < 10 or proof not in story:
            errors.append(f"主线理解门未通过：{label}")
    covered = review.get("covered_checks")
    if not isinstance(covered, list) or any(item not in covered for item in REQUIRED_CHECKS):
        errors.append("主线复检覆盖不完整")
    evidence = review.get("evidence") if isinstance(review.get("evidence"), list) else []
    by_check = {str(item.get("check")): item for item in evidence if isinstance(item, dict)}
    for check in REQUIRED_CHECKS:
        item = by_check.get(check, {})
        proof = str(item.get("proof") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        if len(proof) < 10 or proof not in story or len(explanation) < 8:
            errors.append(f"主线复检证据不完整：{check}")
    if review.get("issues") != []:
        errors.append("主线复检仍有未解决问题")
    for key in ("mainline_sha256", "stage_two_input_sha256"):
        if review.get(key) != packet_value.get(key):
            errors.append(f"主线复检未绑定当前材料：{key}")
    return list(dict.fromkeys(errors))


def seal(cache_root: Path, review_path: Path) -> Path:
    packet_value = packet(cache_root)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    errors = validate_review(packet_value, review)
    if errors:
        raise ValueError("；".join(errors))
    output = cache_root / "mainline-story-review.json"
    output.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def verify(cache_root: Path) -> list[str]:
    try:
        packet_value = packet(cache_root)
        path = cache_root / "mainline-story-review.json"
        if not path.is_file():
            return ["缺少冻结主线当前有效回执"]
        return validate_review(packet_value, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("packet"); p.add_argument("cache_root", type=Path); p.add_argument("--output", type=Path)
    s = sub.add_parser("seal"); s.add_argument("cache_root", type=Path); s.add_argument("review", type=Path)
    v = sub.add_parser("verify"); v.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "packet":
            value = json.dumps(packet(args.cache_root), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.write_text(value, encoding="utf-8")
                print(f"PASS: {args.output}")
            else:
                print(value, end="")
        elif args.command == "seal":
            print(f"PASS: {seal(args.cache_root, args.review)}")
        else:
            errors = verify(args.cache_root)
            if errors:
                for error in errors: print(f"FAIL: {error}")
                return 1
            print("PASS: linear mainline has a current review receipt")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
