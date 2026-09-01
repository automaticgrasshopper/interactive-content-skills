#!/usr/bin/env python3
"""Atomically accept one node screenplay; never writes or replaces the route."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from build_enhancer_input import build as build_enhancer_input
from screenplay_contract import seal
from stage_contract import RECEIPT_VERSION, build_packet, context_dramatic_state, digest
from validate_compact_draft import validate as validate_compact_draft


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("formal_route", type=Path)
    parser.add_argument("node_context", type=Path)
    parser.add_argument("writing_packet", type=Path)
    parser.add_argument("compact_draft", type=Path)
    parser.add_argument("compact_receipt", type=Path)
    parser.add_argument("enhancer_input", type=Path)
    parser.add_argument("enhanced_screenplay", type=Path)
    parser.add_argument("node_draft", type=Path)
    parser.add_argument("node_patch", type=Path)
    parser.add_argument("--accepted-at")
    parser.add_argument("--plan-index", type=Path)
    args = parser.parse_args()
    try:
        route = json.loads(args.formal_route.read_text(encoding="utf-8"))
        context = json.loads(args.node_context.read_text(encoding="utf-8"))
        packet = args.writing_packet.read_text(encoding="utf-8")
        compact = args.compact_draft.read_text(encoding="utf-8").strip()
        receipt = json.loads(args.compact_receipt.read_text(encoding="utf-8"))
        enhancer_input = args.enhancer_input.read_text(encoding="utf-8")
        enhanced = args.enhanced_screenplay.read_text(encoding="utf-8").strip()
        draft = json.loads(args.node_draft.read_text(encoding="utf-8"))
        plan_index = json.loads(args.plan_index.read_text(encoding="utf-8")) if args.plan_index else None

        node_id = str(draft.get("node_id") or "")
        expected_packet = build_packet(route, context, node_id, plan_index)
        if packet != expected_packet:
            raise ValueError("写作包不是由当前正式路线与上下文生成")
        compact_issues = validate_compact_draft(packet, compact)
        if compact_issues:
            raise ValueError("；".join(compact_issues))
        if receipt.get("contract_version") != RECEIPT_VERSION or receipt.get("status") != "PASS":
            raise ValueError("行动底稿回执无效")
        if receipt.get("writing_packet_sha256") != digest(packet) or receipt.get("compact_draft_sha256") != digest(compact):
            raise ValueError("行动底稿回执哈希失效")

        root = Path(__file__).resolve().parents[1]
        enhancer_reference = (root / "references" / "full-scene-enhancer.md").read_text(encoding="utf-8")
        quality_reference = (root / "references" / "dialogue-and-quality.md").read_text(encoding="utf-8")
        expected_enhancer_input = build_enhancer_input(packet, compact, receipt, enhancer_reference, quality_reference)
        if enhancer_input != expected_enhancer_input:
            raise ValueError("Enhancer输入未绑定当前写作包、底稿或reference")
        screenplay = ((draft.get("screenplay") or {}).get("分集剧本") or {}).get("完整剧本")
        if not enhanced or str(screenplay or "").strip() != enhanced:
            raise ValueError("正式正文必须逐字等于当前完整增强稿")
        accepted = seal(
            route,
            draft,
            args.accepted_at,
            prior_state=context_dramatic_state(route, context, node_id),
        )
        atomic_json(args.node_patch, accepted)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"NODE_SCREENPLAY_REJECTED: {error}")
        return 1
    print("NODE_SCREENPLAY_ACCEPTED")
    print(f"NODE_ID={accepted['node_id']}")
    print(f"SCREENPLAY_HASH={accepted['screenplay_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
