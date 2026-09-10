#!/usr/bin/env python3
"""Parse and verify explicit route counts from the user's own request."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


HARD_COUNT_FIELDS = {
    "episode_count",
    "choice_node_count",
    "ending_count",
    "total_node_count",
}
_NUMBER = r"(?:\d+|[零〇一二两三四五六七八九十百]+)"


def _number(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if "百" in value:
        head, tail = value.split("百", 1)
        return digits.get(head, 1) * 100 + (_number(tail) if tail else 0)
    if "十" in value:
        head, tail = value.split("十", 1)
        return digits.get(head, 1) * 10 + (digits.get(tail, 0) if tail else 0)
    result = 0
    for character in value:
        if character not in digits:
            raise ValueError(f"无法解析用户数量：{value}")
        result = result * 10 + digits[character]
    return result


def _unique_count(text: str, patterns: tuple[str, ...], label: str) -> int | None:
    values = {
        _number(match.group("count"))
        for pattern in patterns
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
    }
    if len(values) > 1:
        raise ValueError(f"用户原话中的{label}数量互相冲突：{sorted(values)}")
    return next(iter(values), None)


def parse_explicit_counts(text: str) -> dict[str, int | None]:
    """Return only counts stated in the user text; never infer missing counts."""
    if not isinstance(text, str):
        raise ValueError("user-request.md必须是文本")
    total_node_count = _unique_count(
        text,
        (
            rf"(?:总共|一共|合计)\s*(?P<count>{_NUMBER})\s*(?:张|个)?(?:卡|节点)"
            rf"[^。；;\n]{{0,18}}(?:包含|含|包括)[^。；;\n]{{0,12}}(?:选择卡|选择节点|抉择点|选择点)",
        ),
        "总卡片",
    )
    episode_count = _unique_count(
        text,
        (
            rf"(?P<count>{_NUMBER})\s*集(?:剧情|内容)?",
            rf"(?P<count>{_NUMBER})\s*个\s*(?:剧情|内容)(?:节点|卡)",
            rf"(?P<count>{_NUMBER})\s*张\s*(?:剧情|内容)卡",
            rf"(?P<count>{_NUMBER})\s*个\s*节点(?![^。；;\n]{{0,18}}(?:包含|含|包括)[^。；;\n]{{0,12}}(?:选择卡|选择节点|抉择点|选择点))",
        ),
        "剧情内容节点",
    )
    choice_node_count = _unique_count(
        text,
        (
            rf"(?P<count>{_NUMBER})\s*个?\s*(?:抉择点|选择点|决策点|分支选择|选择节点|分支节点|抉择节点|决策节点|分支点)",
        ),
        "选择节点",
    )
    ending_count = _unique_count(
        text,
        (rf"(?P<count>{_NUMBER})\s*个?\s*结局",),
        "结局",
    )
    if re.search(r"(?:不要|不设|不需要|没有|无)(?:任何)?(?:选择(?:节点|点)?|抉择点|分支(?:节点)?)", text):
        if choice_node_count not in (None, 0):
            raise ValueError("用户同时要求无选择和非零选择数量")
        choice_node_count = 0
    return {
        "episode_count": episode_count,
        "choice_node_count": choice_node_count,
        "ending_count": ending_count,
        "total_node_count": total_node_count,
    }


def validate_intent_lock(user_text: str, intent: Any, errors: list[str]) -> None:
    hard_counts = intent.get("hard_counts") if isinstance(intent, dict) else None
    if not isinstance(hard_counts, dict) or set(hard_counts) != HARD_COUNT_FIELDS:
        errors.append("用户意图锁必须完整列出四项hard_counts")
        return
    try:
        expected = parse_explicit_counts(user_text)
    except ValueError as error:
        errors.append(str(error))
        return
    for field in HARD_COUNT_FIELDS:
        value = hard_counts[field]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            errors.append(f"用户硬数量非法：{field}")
        elif value != expected[field]:
            errors.append(
                f"用户意图锁与原话不一致：{field}应为{expected[field]}，实际{value}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("user_request", type=Path)
    args = parser.parse_args()
    try:
        result = parse_explicit_counts(args.user_request.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"COUNT_PARSE_REJECTED: {error}")
        return 1
    print(json.dumps({"hard_counts": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
