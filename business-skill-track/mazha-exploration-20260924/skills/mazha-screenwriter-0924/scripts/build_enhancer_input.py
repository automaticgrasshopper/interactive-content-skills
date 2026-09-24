#!/usr/bin/env python3
"""Build the sole complete-rewrite input from a sealed action draft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage_contract import RECEIPT_VERSION, digest


def build(packet: str, draft: str, receipt: dict, enhancer_reference: str, quality_reference: str) -> str:
    if receipt.get("contract_version") != RECEIPT_VERSION or receipt.get("status") != "PASS":
        raise ValueError("缺少有效行动底稿回执")
    if receipt.get("writing_packet_sha256") != digest(packet) or receipt.get("compact_draft_sha256") != digest(draft):
        raise ValueError("行动底稿回执未绑定当前写作包或底稿")
    return (
        "ENHANCER_INPUT_VERSION=nextplay.node-enhancer-input.v1\n"
        f"WRITING_PACKET_SHA256={digest(packet)}\n"
        f"COMPACT_DRAFT_SHA256={digest(draft)}\n"
        f"ENHANCER_REFERENCE_SHA256={digest(enhancer_reference)}\n"
        f"QUALITY_REFERENCE_SHA256={digest(quality_reference)}\n\n"
        "# Frozen Node Writing Packet\n" + packet.strip() + "\n\n"
        "# Full Scene Enhancer\n" + enhancer_reference.strip() + "\n\n"
        "# Dialogue And Quality\n" + quality_reference.strip() + "\n\n"
        "# Sealed Compact Action Draft\n" + draft.strip() + "\n"
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
