#!/usr/bin/env python3
"""Seal a compact dramatic draft before the sole full screenplay rewrite."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

VERSION = "nextplay.compact-draft-receipt.v1"
SCENE = re.compile(r"(?m)^【[^】]+·[^】]+·(?:内|外)】\s*$")
DIALOGUE = re.compile(r"(?m)^[^\s【#][^：\n]{0,15}：\S.+$")
BANNED = (
    "这一集", "本集", "按梗概", "既定动作", "依次说明情况", "停止边界",
    "冲突继续", "推进到", "根据现场反馈", "场内人物", "后续剧情",
)
CHANGE_MARKERS = ("变成", "转为", "降到", "升到", "停下", "熄灭", "亮起", "断开", "接通", "弹出", "显示", "响起", "恢复", "失效")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate(text: str) -> list[str]:
    compact = text.strip()
    issues: list[str] = []
    if not 350 <= len(compact) <= 1800:
        issues.append("短底稿应在350至1800字之间，只保留完整行动链")
    if not SCENE.search(compact):
        issues.append("短底稿缺少合法场次标题")
    if len(DIALOGUE.findall(compact)) < 2:
        issues.append("短底稿缺少推动行动的实际话轮")
    action_lines = [
        line.strip() for line in compact.splitlines()
        if line.strip() and not SCENE.fullmatch(line.strip()) and not DIALOGUE.fullmatch(line.strip())
    ]
    if len(action_lines) < 4:
        issues.append("短底稿缺少动作、阻力、反馈与结果")
    if not any(marker in compact for marker in CHANGE_MARKERS):
        issues.append("短底稿没有写出行动造成的可见或可听状态变化")
    found = [term for term in BANNED if term in compact]
    if found:
        issues.append(f"短底稿含制作元话语或占位文本：{found}")
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
            raise ValueError("；".join(issues))
        receipt = {
            "contract_version": VERSION,
            "episode_id": args.episode_id,
            "compact_draft_sha256": sha(text),
            "status": "PASS",
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: {args.episode_id} compact draft is sealed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
