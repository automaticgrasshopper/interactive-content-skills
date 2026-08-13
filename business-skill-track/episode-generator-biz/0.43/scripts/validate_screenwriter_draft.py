#!/usr/bin/env python3
"""Reject empty, placeholder, or non-dramatized Screenwriter drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

VERSION = "nextplay.screenwriter-receipt.v1"
SCENE = re.compile(r"(?m)^【[^】]+·[^】]+·(?:内|外)】\s*$")
DIALOGUE = re.compile(r"(?m)^[^\s【#][^：\n]{0,15}：\S.+$")
BANNED = (
    "这一集", "本集", "按梗概", "既定动作", "依次说明情况", "停止边界",
    "冲突继续", "推进到", "根据现场反馈", "场内人物", "后续剧情",
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate(text: str) -> list[str]:
    issues: list[str] = []
    compact = text.strip()
    if len(compact) < 350:
        issues.append("Screenwriter原稿过短，尚未形成完整可表演场景")
    if not SCENE.search(compact):
        issues.append("Screenwriter原稿缺少合法场次标题")
    if len(DIALOGUE.findall(compact)) < 4:
        issues.append("Screenwriter原稿缺少足够的实际人物话轮")
    action_lines = [
        line.strip() for line in compact.splitlines()
        if line.strip() and not SCENE.fullmatch(line.strip()) and not DIALOGUE.fullmatch(line.strip())
    ]
    if len(action_lines) < 5:
        issues.append("Screenwriter原稿缺少动作、现场反馈与人物调整")
    found = [term for term in BANNED if term in compact]
    if found:
        issues.append(f"Screenwriter原稿含制作元话语或占位文本：{found}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        text = args.draft.read_text(encoding="utf-8").strip()
        issues = validate(text)
        if issues:
            for issue in issues:
                print(f"FAIL: {issue}")
            return 1
        receipt = {
            "contract_version": VERSION,
            "episode_id": args.episode_id,
            "draft_sha256": sha(text),
            "status": "PASS",
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: {args.episode_id} Screenwriter draft is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
