#!/usr/bin/env python3
"""Build one sealed topology packet and require two serial review passes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PACKET_VERSION = "nextplay.topology-review-packet.v1"
REVIEW_VERSION = "nextplay.topology-double-review.v2"
MATERIAL_NAMES = (
    "complete-story.json",
    "mainline-decomposition.json",
    "decision-fissure-audit.json",
    "story-treatment.json",
    "topology.md",
    "mainline-path.json",
    "route-duration.json",
)
REQUIRED_CHECKS = (
    "主线投影无遗漏改写",
    "采用的决定裂缝真实成立",
    "选项即时后果互异且可见",
    "未结束路线持续承接差异",
    "汇合具有共同事实基础",
    "主结局忠实落下冻结完整故事",
    "期望结局充分兑现核心目标与类型期待",
    "失败结局在核心故事内推进后完成失败结算",
    "至少一个小结局因永久离开核心故事而成立且没有为数量补形状",
    "每个节点是完整可演戏剧单位",
    "节点总量没有注水或压缩",
)
ROOT_FIELDS = {"contract_version", "packet_sha256", "review_pass", "verdict", "checks", "issues"}
CHECK_FIELDS = {"check", "passed", "explanation", "evidence"}
EVIDENCE_FIELDS = {"artifact", "quote"}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def packet(cache_root: Path) -> dict[str, Any]:
    materials: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for name in MATERIAL_NAMES:
        path = cache_root / name
        if not path.is_file():
            raise ValueError(f"拓扑复检缺少材料：{name}")
        text = path.read_text(encoding="utf-8")
        materials[name] = text
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "packet_version": PACKET_VERSION,
        "task_contract": "当前任务串行完成A、B两遍完整复检；每遍只从本材料包重新判断，只返回规定JSON，不修改材料，也不复制另一遍结论。",
        "review_lenses": {
            "A": "从故事投影、决定裂缝、动作后果、持续差异和汇合基础复检。",
            "B": "从路线完整性、结局兑现、戏剧单位必要性和整体形状压力复检。",
        },
        "required_checks": list(REQUIRED_CHECKS),
        "material_sha256": hashes,
        "materials": materials,
    }


def packet_sha256(cache_root: Path) -> str:
    return digest(packet(cache_root))


def validate_review(cache_root: Path, review: Any, slot: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(review, dict) or set(review) != ROOT_FIELDS:
        return ["拓扑双复检根字段错误"]
    current_packet = packet(cache_root)
    if review.get("contract_version") != REVIEW_VERSION:
        errors.append("拓扑双复检合同版本错误")
    if review.get("packet_sha256") != digest(current_packet):
        errors.append("拓扑双复检未绑定当前封闭材料包")
    review_pass = str(review.get("review_pass") or "").upper()
    if review_pass not in {"A", "B"} or (slot and review_pass != slot.upper()):
        errors.append("拓扑复检遍次与封存位置不一致")
    verdict = review.get("verdict")
    if verdict not in {"PASS", "FAIL"}:
        errors.append("拓扑双复检 verdict 非法")
    issues = review.get("issues")
    if not isinstance(issues, list) or any(not isinstance(item, str) or not item.strip() for item in issues):
        errors.append("拓扑双复检 issues 必须是非空字符串数组或空数组")
        issues = []
    checks = review.get("checks")
    if not isinstance(checks, list):
        return errors + ["拓扑双复检 checks 必须是数组"]
    by_name: dict[str, dict[str, Any]] = {}
    for item in checks:
        if not isinstance(item, dict) or set(item) != CHECK_FIELDS:
            errors.append("拓扑双复检检查项字段错误")
            continue
        name = str(item.get("check") or "")
        if name in by_name:
            errors.append(f"拓扑双复检检查项重复：{name}")
        by_name[name] = item
    if set(by_name) != set(REQUIRED_CHECKS):
        errors.append("拓扑双复检未完整覆盖固定检查集合")
    materials = current_packet["materials"]
    failed = 0
    for name in REQUIRED_CHECKS:
        item = by_name.get(name) or {}
        passed = item.get("passed")
        if not isinstance(passed, bool):
            errors.append(f"拓扑双复检 passed 非布尔值：{name}")
        elif not passed:
            failed += 1
        if len(str(item.get("explanation") or "").strip()) < 8:
            errors.append(f"拓扑双复检缺少判断说明：{name}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"拓扑双复检缺少材料证据：{name}")
            continue
        for proof in evidence:
            if not isinstance(proof, dict) or set(proof) != EVIDENCE_FIELDS:
                errors.append(f"拓扑双复检证据字段错误：{name}")
                continue
            artifact = str(proof.get("artifact") or "")
            quote = str(proof.get("quote") or "").strip()
            if artifact not in materials or len(quote) < 8 or quote not in materials.get(artifact, ""):
                errors.append(f"拓扑双复检证据不在当前材料中：{name}/{artifact}")
    if verdict == "PASS" and (failed or issues):
        errors.append("拓扑双复检 PASS 与失败检查或问题单冲突")
    if verdict == "FAIL" and (failed == 0 or not issues):
        errors.append("拓扑双复检 FAIL 必须包含失败检查和问题单")
    return list(dict.fromkeys(errors))


def seal(cache_root: Path, review_path: Path, slot: str) -> Path:
    review = json.loads(review_path.read_text(encoding="utf-8"))
    errors = validate_review(cache_root, review, slot)
    if errors:
        raise ValueError("；".join(errors))
    output = cache_root / f"topology-review-{slot}.json"
    output.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def verify(cache_root: Path) -> list[str]:
    errors: list[str] = []
    for slot in ("a", "b"):
        path = cache_root / f"topology-review-{slot}.json"
        if not path.is_file():
            errors.append(f"缺少拓扑复检回执：{slot}")
            continue
        try:
            review = json.loads(path.read_text(encoding="utf-8"))
            errors.extend(f"复检{slot}：{error}" for error in validate_review(cache_root, review, slot))
            if isinstance(review, dict) and review.get("verdict") != "PASS":
                errors.append(f"拓扑复检{slot}未通过")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"拓扑复检{slot}不可读：{error}")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("packet")
    make.add_argument("cache_root", type=Path)
    make.add_argument("--output", type=Path)
    for command, slot in (("seal-a", "a"), ("seal-b", "b")):
        seal_parser = sub.add_parser(command)
        seal_parser.add_argument("cache_root", type=Path)
        seal_parser.add_argument("review", type=Path)
        seal_parser.set_defaults(slot=slot)
    check = sub.add_parser("verify")
    check.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "packet":
            value = packet(args.cache_root)
            text = json.dumps({**value, "packet_sha256": digest(value)}, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.write_text(text, encoding="utf-8")
                print(f"PASS: {args.output}")
            else:
                print(text, end="")
        elif args.command in {"seal-a", "seal-b"}:
            print(f"PASS: {seal(args.cache_root, args.review, args.slot)}")
        else:
            errors = verify(args.cache_root)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}")
                return 1
            print("PASS: two serial topology review passes accepted the same current packet")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
