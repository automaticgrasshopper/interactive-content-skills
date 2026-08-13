#!/usr/bin/env python3
"""Build the sole Enhancer input with both rewrite references embedded verbatim."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


RECEIPT_VERSION = "nextplay.screenwriter-receipt.v1"


def build(draft: Path, boundary: str, enhancer_reference: Path, dialogue_reference: Path, screenwriter_receipt: Path) -> str:
    draft_text = draft.read_text(encoding="utf-8").strip()
    enhancer_text = enhancer_reference.read_text(encoding="utf-8").strip()
    dialogue_text = dialogue_reference.read_text(encoding="utf-8").strip()
    boundary = boundary.strip()
    if not draft_text or not enhancer_text or not dialogue_text or len(boundary) < 12:
        raise ValueError("Enhancer输入缺少草稿、停止边界或完整reference")
    receipt = json.loads(screenwriter_receipt.read_text(encoding="utf-8"))
    if receipt.get("contract_version") != RECEIPT_VERSION or receipt.get("status") != "PASS":
        raise ValueError("缺少有效的Screenwriter完成回执")
    if receipt.get("draft_sha256") != digest(draft_text):
        raise ValueError("Screenwriter完成回执未绑定当前草稿")
    return (
        "ENHANCER_INPUT_VERSION=nextplay.enhancer-input.v1\n"
        f"DRAFT_SHA256={digest(draft_text)}\n"
        f"ENHANCER_REFERENCE_SHA256={digest(enhancer_text)}\n"
        f"DIALOGUE_REFERENCE_SHA256={digest(dialogue_text)}\n\n"
        "# 当前集停止边界\n" + boundary + "\n\n"
        "# ViMax Script Enhancer Reference\n" + enhancer_text + "\n\n"
        "# Chinese Dialogue Craft Reference\n" + dialogue_text + "\n\n"
        "# Screenwriter Draft\n" + draft_text + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--boundary", required=True)
    parser.add_argument("--enhancer-reference", type=Path, required=True)
    parser.add_argument("--dialogue-reference", type=Path, required=True)
    parser.add_argument("--screenwriter-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = build(args.draft, args.boundary, args.enhancer_reference, args.dialogue_reference, args.screenwriter_receipt)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value, encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
