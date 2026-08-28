#!/usr/bin/env python3
"""Build an anonymous two-topology comparison and seal the selected candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from route_contract import validate as validate_route


PACKET_VERSION = "nextplay.topology-blind-comparison.v1"
VERDICT_VERSION = "nextplay.topology-blind-verdict.v1"
SELECTION_VERSION = "nextplay.topology-selection.v1"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
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


def compact_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    for node in candidate["nodes"]:
        material = node["route_material"]
        nodes.append({
            "node_id": node["node_id"],
            "title": node["分集标题"],
            "synopsis": material["单集梗概"],
            "conflict": material["本集冲突"],
            "entry_state": material["entry_state"],
            "state_changes": material["state_changes"],
            "stop_boundary": material["stop_boundary"],
            "successors": node["后续节点编号列表"],
            "ending_type": node["ending_type"],
            "interaction": node["互动节点"],
        })
    return {"nodes": nodes}


def load_drafts(cache_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    first = load_json(cache_root / "topology-draft-1.json")
    second = load_json(cache_root / "topology-draft-2.json")
    for label, candidate in (("第一版", first), ("第二版", second)):
        issues = validate_route(candidate, require_accepted=False)
        if issues:
            raise ValueError(f"{label}不是完整合法候选：" + "；".join(issues))
    for field in ("project_id", "route_id", "route_version", "route_input_hash"):
        if first[field] != second[field]:
            raise ValueError(f"两版拓扑的{field}不一致")
    if digest(compact_candidate(first)) == digest(compact_candidate(second)):
        raise ValueError("两版拓扑没有形成可比较的内容差异")
    return first, second


def label_mapping(first: dict[str, Any], second: dict[str, Any]) -> dict[str, str]:
    seed = digest({
        "route_input_hash": first["route_input_hash"],
        "first": digest(first),
        "second": digest(second),
    })
    return {"X": "draft-1", "Y": "draft-2"} if int(seed[-1], 16) % 2 == 0 else {"X": "draft-2", "Y": "draft-1"}


def build_packet(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    drafts = {"draft-1": first, "draft-2": second}
    mapping = label_mapping(first, second)
    return {
        "contract_version": PACKET_VERSION,
        "question": "在同样忠实于故事和情绪脊的前提下，哪一版明显拥有更丰富、自然且持续生效的互动变化，同时没有明显注水？",
        "instructions": "匿名比较一次；不打分、不计数、不混合两版、不生成第三版。只有差距明显时指定胜者；没有明显差距时clear_advantage=false。",
        "candidates": {
            label: compact_candidate(drafts[source])
            for label, source in mapping.items()
        },
    }


def validate_verdict(verdict: Any, packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {"contract_version", "clear_advantage", "winner", "reason", "evidence"}
    if not isinstance(verdict, dict) or set(verdict) != expected:
        return ["匿名比较回执字段错误"]
    if verdict["contract_version"] != VERDICT_VERSION:
        errors.append("匿名比较回执版本错误")
    if not isinstance(verdict["clear_advantage"], bool):
        errors.append("clear_advantage必须为布尔值")
    if verdict["clear_advantage"] is True and verdict["winner"] not in {"X", "Y"}:
        errors.append("存在明显差距时winner必须是X或Y")
    if verdict["clear_advantage"] is False and verdict["winner"] is not None:
        errors.append("没有明显差距时winner必须为null")
    if len(str(verdict["reason"] or "").strip()) < 12:
        errors.append("匿名比较理由不足")
    evidence = verdict["evidence"]
    corpus = json.dumps(packet["candidates"], ensure_ascii=False)
    if not isinstance(evidence, list) or not evidence:
        errors.append("匿名比较缺少逐字证据")
    elif any(len(str(item).strip()) < 6 or str(item) not in corpus for item in evidence):
        errors.append("匿名比较证据必须逐字来自匿名候选")
    return errors


def build_selection(
    first: dict[str, Any],
    second: dict[str, Any],
    packet: dict[str, Any],
    verdict: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_packet = build_packet(first, second)
    if packet != expected_packet:
        raise ValueError("匿名比较包已失效")
    issues = validate_verdict(verdict, packet)
    if issues:
        raise ValueError("；".join(issues))
    mapping = label_mapping(first, second)
    selected_source = mapping[verdict["winner"]] if verdict["clear_advantage"] else "draft-2"
    selected = deepcopy(first if selected_source == "draft-1" else second)
    receipt = {
        "contract_version": SELECTION_VERSION,
        "status": "PASS",
        "packet_hash": digest(packet),
        "verdict_hash": digest(verdict),
        "draft_1_hash": digest(first),
        "draft_2_hash": digest(second),
        "selected_source": selected_source,
        "selected_hash": digest(selected),
        "clear_advantage": verdict["clear_advantage"],
        "reason": verdict["reason"],
    }
    return receipt, selected


def verify_root(cache_root: Path) -> list[str]:
    try:
        first, second = load_drafts(cache_root)
        packet = load_json(cache_root / "topology-comparison-packet.json")
        verdict = load_json(cache_root / "topology-comparison-verdict.json")
        receipt = load_json(cache_root / "topology-selection.json")
        candidate = load_json(cache_root / "route-candidate.json")
        expected_receipt, expected_candidate = build_selection(first, second, packet, verdict)
        errors: list[str] = []
        if receipt != expected_receipt:
            errors.append("拓扑选择回执已失效")
        if candidate != expected_candidate:
            errors.append("正式候选不是匿名比较选中的原版拓扑")
        return errors
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    packet_parser = sub.add_parser("packet")
    packet_parser.add_argument("cache_root", type=Path)
    packet_parser.add_argument("--output", required=True, type=Path)
    seal_parser = sub.add_parser("seal")
    seal_parser.add_argument("cache_root", type=Path)
    seal_parser.add_argument("verdict", type=Path)
    materialize_parser = sub.add_parser("materialize")
    materialize_parser.add_argument("cache_root", type=Path)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "packet":
            first, second = load_drafts(args.cache_root)
            atomic_json(args.output, build_packet(first, second))
            print("TOPOLOGY_COMPARISON_PACKET_READY")
        elif args.command == "seal":
            first, second = load_drafts(args.cache_root)
            packet = load_json(args.cache_root / "topology-comparison-packet.json")
            verdict = load_json(args.verdict)
            receipt, candidate = build_selection(first, second, packet, verdict)
            atomic_json(args.cache_root / "topology-selection.json", receipt)
            print("TOPOLOGY_SELECTED")
            print(f"SELECTED_SOURCE={receipt['selected_source']}")
        elif args.command == "materialize":
            first, second = load_drafts(args.cache_root)
            packet = load_json(args.cache_root / "topology-comparison-packet.json")
            verdict = load_json(args.cache_root / "topology-comparison-verdict.json")
            receipt = load_json(args.cache_root / "topology-selection.json")
            expected_receipt, candidate = build_selection(first, second, packet, verdict)
            if receipt != expected_receipt:
                raise ValueError("拓扑选择回执已失效")
            atomic_json(args.cache_root / "route-candidate.json", candidate)
            print("SELECTED_TOPOLOGY_MATERIALIZED")
        else:
            errors = verify_root(args.cache_root)
            if errors:
                raise ValueError("；".join(errors))
            print("TOPOLOGY_SELECTION_PASS")
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as error:
        print(f"TOPOLOGY_SELECTION_REJECTED: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
