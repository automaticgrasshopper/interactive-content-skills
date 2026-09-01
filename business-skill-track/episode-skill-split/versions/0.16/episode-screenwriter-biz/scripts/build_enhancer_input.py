#!/usr/bin/env python3
"""Build a clean creative input from a machine-verified action draft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage_contract import PACKET_HEADER, RECEIPT_VERSION, digest


def build(packet: str, draft: str, receipt: dict, enhancer_reference: str, quality_reference: str) -> str:
    if receipt.get("contract_version") != RECEIPT_VERSION or receipt.get("status") != "PASS":
        raise ValueError("缺少有效行动底稿回执")
    if receipt.get("writing_packet_sha256") != digest(packet) or receipt.get("compact_draft_sha256") != digest(draft):
        raise ValueError("行动底稿回执未绑定当前写作包或底稿")
    packet_body = packet.removeprefix(PACKET_HEADER).lstrip()
    return (
        "# 完整场景复写入口\n\n"
        "只根据本页内容，把行动底稿完整重写为最终剧本。不要输出分析、合同、检查项或制作说明。\n\n"
        "## 单集写作材料\n\n" + packet_body.strip() + "\n\n"
        "## 已冻结的行动底稿\n\n" + draft.strip() + "\n\n"
        "## 完整场景写作规范\n\n" + enhancer_reference.strip() + "\n\n"
        "## 对白写作规范\n\n" + quality_reference.strip() + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("writing_packet", type=Path)
    parser.add_argument("compact_draft", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        packet = args.writing_packet.read_text(encoding="utf-8")
        draft = args.compact_draft.read_text(encoding="utf-8").strip()
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        enhancer_reference = (root / "references" / "full-scene-enhancer.md").read_text(encoding="utf-8")
        quality_reference = (root / "references" / "dialogue-and-quality.md").read_text(encoding="utf-8")
        value = build(packet, draft, receipt, enhancer_reference, quality_reference)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ENHANCER_INPUT_REJECTED: {error}")
        return 1
    print("ENHANCER_INPUT_ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
