#!/usr/bin/env python3
"""Validate, packet, seal, and verify the complete story written from creative-brief.json."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from validate_creative_brief import validate_frozen as validate_creative_brief


CONTRACT_VERSION = "nextplay.episode-complete-story.v1"
RECEIPT_VERSION = "nextplay.episode-complete-story-review.v1"
ROOT_FIELDS = {"contract_version", "creative_brief_sha256", "title", "complete_story"}
VOLUME_RESULTS = {"aligned", "story-longer-than-signal", "story-shorter-than-signal", "not-provided"}
BRANCH_MARKERS = (
    "玩家可以", "选择A", "选择B", "另一条路线", "另一分支", "如果选择",
    "分集节点", "拓扑结构", "情绪坐标", "开扇", "汇合率",
)
EPISODE_ID = re.compile(r"episode-\d{3}")
VOLUME_LOCK = re.compile(r"(?:故事|篇幅|体量).*(?:必须|固定|控制在)|(?:必须|固定|控制在).*(?:故事|篇幅|体量)")
REQUIRED_CHECKS = (
    "用户硬约束", "开端到结局完整", "连续因果", "人物行动与变化",
    "关键发现过程", "最终结算", "无结构预制",
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_complete_story(cache_root: Path) -> tuple[Path, dict[str, Any]]:
    brief = validate_creative_brief(cache_root)
    path = cache_root / "complete-story.json"
    if not path.is_file():
        raise ValueError("缺少 complete-story.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != ROOT_FIELDS:
        raise ValueError("完整故事根字段错误")
    if value.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(f"完整故事合同错误：期望 {CONTRACT_VERSION}")
    if value.get("creative_brief_sha256") != digest(brief):
        raise ValueError("完整故事未绑定当前 creative-brief.json")
    if str(value.get("title") or "").strip() != str(brief.get("title") or "").strip():
        raise ValueError("完整故事标题与创作简报不一致")
    story = str(value.get("complete_story") or "").strip()
    if len(story) < 500:
        raise ValueError("完整故事过短，尚未形成可连续阅读的完整因果")
    found = [marker for marker in BRANCH_MARKERS if marker in story]
    if found or EPISODE_ID.search(story):
        raise ValueError(f"完整故事提前出现结构语言：{found or ['episode-id']}")
    return path, value


def packet(cache_root: Path) -> dict[str, Any]:
    path, story = read_complete_story(cache_root)
    brief = validate_creative_brief(cache_root)
    return {
        "packet_version": RECEIPT_VERSION,
        "complete_story_path": str(path),
        "complete_story_sha256": digest(story),
        "creative_brief_sha256": digest(brief),
        "required_checks": list(REQUIRED_CHECKS),
        "story_volume_signal": brief.get("story_volume"),
        "user_constraints": brief.get("user_constraints"),
        "complete_story": story,
    }


def validate_review(packet_value: dict[str, Any], review: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in ("complete_story_sha256", "creative_brief_sha256"):
        if review.get(field) != packet_value.get(field):
            issues.append(f"完整故事复检未绑定当前材料：{field}")
    covered = review.get("covered_checks")
    if not isinstance(covered, list) or any(check not in covered for check in REQUIRED_CHECKS):
        issues.append("完整故事复检覆盖不完整")
    evidence = review.get("evidence") if isinstance(review.get("evidence"), list) else []
    by_check = {str(item.get("check")): item for item in evidence if isinstance(item, dict)}
    story_text = str(packet_value["complete_story"]["complete_story"])
    for check in REQUIRED_CHECKS:
        item = by_check.get(check) or {}
        proof = str(item.get("proof") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        if len(proof) < 8 or proof not in story_text or len(explanation) < 8:
            issues.append(f"完整故事复检证据不完整：{check}")
    volume = review.get("volume_assessment")
    if not isinstance(volume, dict) or set(volume) != {"result", "reason", "recommendation"}:
        issues.append("完整故事复检缺少体量比较")
    else:
        result = volume.get("result")
        reason = str(volume.get("reason") or "").strip()
        recommendation = volume.get("recommendation")
        signal = packet_value.get("story_volume_signal")
        locked = any(
            VOLUME_LOCK.search(str(item.get("statement") or ""))
            for item in (packet_value.get("user_constraints") or [])
            if isinstance(item, dict)
        )
        if result not in VOLUME_RESULTS or len(reason) < 8:
            issues.append("体量比较结果或理由非法")
        if signal is None and result != "not-provided":
            issues.append("未提供体量信号时只能使用 not-provided")
        if signal is not None and result == "not-provided":
            issues.append("已提供体量信号时不得使用 not-provided")
        if recommendation not in (None, ""):
            issues.append("体量比较不得制造面向用户的调整建议")
        if locked and result not in {"aligned", "not-provided"}:
            issues.append("用户硬锁体量尚未满足；必须自动返写完整故事")
    if review.get("issues") != []:
        issues.append("完整故事复检仍有未解决问题")
    return list(dict.fromkeys(issues))


def seal(cache_root: Path, review_path: Path) -> Path:
    packet_value = packet(cache_root)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    issues = validate_review(packet_value, review)
    if issues:
        raise ValueError("；".join(issues))
    output = cache_root / "complete-story-review.json"
    output.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def verify(cache_root: Path) -> list[str]:
    try:
        packet_value = packet(cache_root)
        path = cache_root / "complete-story-review.json"
        if not path.is_file():
            return ["缺少完整故事当前有效回执"]
        return validate_review(packet_value, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    packet_parser = sub.add_parser("packet")
    packet_parser.add_argument("cache_root", type=Path)
    packet_parser.add_argument("--output", type=Path)
    seal_parser = sub.add_parser("seal")
    seal_parser.add_argument("cache_root", type=Path)
    seal_parser.add_argument("review", type=Path)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "packet":
            text = json.dumps(packet(args.cache_root), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.write_text(text, encoding="utf-8")
                print(f"PASS: {args.output}")
            else:
                print(text, end="")
        elif args.command == "seal":
            print(f"PASS: {seal(args.cache_root, args.review)}")
        else:
            issues = verify(args.cache_root)
            if issues:
                for issue in issues:
                    print(f"FAIL: {issue}")
                return not_accepted(__file__)
            print("PASS: complete story has a current review receipt")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
