#!/usr/bin/env python3
"""Seal a compact action draft without using length or dialogue quotas."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from stage_contract import PACKET_VERSION, RECEIPT_VERSION, digest

SCENE = re.compile(r"(?m)^【[^【】\n]+·[^【】\n]+·(?:内|外)】\s*$")
DIALOGUE = re.compile(r"^[^\s：:【】]{1,20}：\s*\S+$")
BANNED = ("停止边界", "按梗概", "本节点", "后续节点", "创作分析", "验收结论", "选项A", "选项B")


def action_blocks(text: str) -> list[str]:
    blocks = [item.strip() for item in re.split(r"\n\s*\n", text.strip()) if item.strip()]
    return [item for item in blocks if SCENE.fullmatch(item) is None and DIALOGUE.fullmatch(item) is None]


def validate(packet: str, draft: str) -> list[str]:
    issues: list[str] = []
    if not packet.startswith(f"WRITING_PACKET_VERSION={PACKET_VERSION}\n"):
        issues.append("写作包版本错误")
    if not draft.strip():
        issues.append("行动底稿为空")
        return issues
    if SCENE.search(draft) is None:
        issues.append("行动底稿缺少合法场次标题")
    if not action_blocks(draft):
        issues.append("行动底稿缺少实际动作、阻力或结果")
    found = [term for term in BANNED if term in draft]
    if found:
        issues.append(f"行动底稿含制作元话语：{found}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("writing_packet", type=Path)
    parser.add_argument("compact_draft", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        packet = args.writing_packet.read_text(encoding="utf-8")
        draft = args.compact_draft.read_text(encoding="utf-8").strip()
        issues = validate(packet, draft)
        if issues:
            raise ValueError("；".join(issues))
        receipt = {
            "contract_version": RECEIPT_VERSION,
            "writing_packet_sha256": digest(packet),
            "compact_draft_sha256": digest(draft),
            "status": "PASS",
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"COMPACT_DRAFT_REJECTED: {error}")
        return 1
    print("COMPACT_DRAFT_ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
