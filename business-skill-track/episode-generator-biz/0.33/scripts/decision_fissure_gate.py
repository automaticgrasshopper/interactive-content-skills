#!/usr/bin/env python3
"""Freeze and review the exhaustive pre-topology decision-fissure audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from mainline_story_gate import canonical, read_mainline, verify as verify_mainline


CONTRACT_VERSION = "nextplay.decision-fissure-audit.v1"
RECEIPT_VERSION = "nextplay.decision-fissure-review.v1"
ROOT_FIELDS = {"contract_version", "mainline_sha256", "fissures"}
FISSURE_FIELDS = {"fissure_id", "mainline_position_proof", "decision_question", "actions", "disposition", "disposition_reason"}
ACTION_FIELDS = {"action_id", "action_text", "immediate_consequence", "core_goal_status", "route_ended", "ending_reason"}
GOAL_STATES = {"continuing", "achieved", "failed", "abandoned", "unreachable"}
DISPOSITIONS = {"adopt", "reject-causally-insufficient"}
REQUIRED_CHECKS = [
    "从开场到结局完整扫描决定裂缝",
    "动作当时可执行且彼此互斥",
    "每个动作先写即时后果",
    "即时后果后判断核心目标状态",
    "因果充分的结束动作全部采用",
    "较弱汇合选择未替代较早结局机会",
]


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def all_text(value: Any) -> str:
    if isinstance(value, str): return value
    if isinstance(value, list): return "\n".join(all_text(item) for item in value)
    if isinstance(value, dict): return "\n".join(all_text(item) for item in value.values())
    return ""


def read_audit(cache_root: Path) -> tuple[Path, dict[str, Any]]:
    errors = verify_mainline(cache_root)
    if errors:
        raise ValueError("冻结主线未通过：" + "；".join(errors))
    _, mainline = read_mainline(cache_root)
    story = str(mainline["complete_story"])
    path = cache_root / "decision-fissure-audit.json"
    if not path.is_file():
        raise ValueError("缺少决策裂缝审计：decision-fissure-audit.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        raise ValueError("决策裂缝审计根字段错误")
    if data.get("contract_version") != CONTRACT_VERSION or data.get("mainline_sha256") != digest(mainline):
        raise ValueError("决策裂缝审计合同或主线绑定错误")
    fissures = data.get("fissures")
    if not isinstance(fissures, list) or not fissures:
        raise ValueError("决策裂缝审计至少需要一个候选")
    fissure_ids: set[str] = set()
    action_ids: set[str] = set()
    adopted = 0
    for index, fissure in enumerate(fissures, 1):
        if not isinstance(fissure, dict) or set(fissure) != FISSURE_FIELDS:
            raise ValueError(f"决策裂缝字段错误：第{index}项")
        fissure_id = str(fissure.get("fissure_id") or "")
        proof = str(fissure.get("mainline_position_proof") or "").strip()
        if not fissure_id.startswith("fissure-") or fissure_id in fissure_ids:
            raise ValueError(f"决策裂缝编号非法或重复：{fissure_id}")
        if len(proof) < 12 or proof not in story:
            raise ValueError(f"决策裂缝位置证据不在冻结主线：{fissure_id}")
        if len(str(fissure.get("decision_question") or "").strip()) < 6:
            raise ValueError(f"决策问题过短：{fissure_id}")
        disposition = fissure.get("disposition")
        if disposition not in DISPOSITIONS or len(str(fissure.get("disposition_reason") or "").strip()) < 10:
            raise ValueError(f"候选取舍无有效理由：{fissure_id}")
        actions = fissure.get("actions")
        if not isinstance(actions, list) or len(actions) < 2:
            raise ValueError(f"候选至少需要两个动作：{fissure_id}")
        ended = False
        action_texts: set[str] = set()
        consequences: set[str] = set()
        for action in actions:
            if not isinstance(action, dict) or set(action) != ACTION_FIELDS:
                raise ValueError(f"候选动作字段错误：{fissure_id}")
            action_id = str(action.get("action_id") or "")
            action_text = str(action.get("action_text") or "").strip()
            consequence = str(action.get("immediate_consequence") or "").strip()
            state = action.get("core_goal_status")
            route_ended = action.get("route_ended")
            reason = str(action.get("ending_reason") or "").strip()
            if not action_id or action_id in action_ids or len(action_text) < 2 or action_text in action_texts:
                raise ValueError(f"候选动作编号或文字非法：{fissure_id}/{action_id}")
            if len(consequence) < 10 or consequence in consequences or state not in GOAL_STATES or not isinstance(route_ended, bool):
                raise ValueError(f"候选动作后果或目标状态非法：{fissure_id}/{action_id}")
            if route_ended != (state != "continuing"):
                raise ValueError(f"路线结束判断与核心目标状态矛盾：{fissure_id}/{action_id}")
            if route_ended and len(reason) < 12:
                raise ValueError(f"结束动作缺少因果充分理由：{fissure_id}/{action_id}")
            if not route_ended and reason not in {"", "未结束"}:
                raise ValueError(f"继续动作不得伪造结局理由：{fissure_id}/{action_id}")
            ended = ended or route_ended
            action_ids.add(action_id); action_texts.add(action_text); consequences.add(consequence)
        if ended and disposition != "adopt":
            raise ValueError(f"含因果充分结束动作的裂缝必须采用：{fissure_id}")
        adopted += disposition == "adopt"
        fissure_ids.add(fissure_id)
    if adopted == 0:
        raise ValueError("决策裂缝审计没有采用任何候选")
    return path, data


def packet(cache_root: Path) -> dict[str, Any]:
    path, audit = read_audit(cache_root)
    _, mainline = read_mainline(cache_root)
    return {"packet_version": RECEIPT_VERSION, "audit_path": str(path), "audit_sha256": digest(audit), "mainline_sha256": digest(mainline), "required_checks": REQUIRED_CHECKS, "mainline": mainline, "audit": audit}


def validate_review(packet_value: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    corpus = all_text(packet_value["mainline"]) + "\n" + all_text(packet_value["audit"])
    for key in ("audit_sha256", "mainline_sha256"):
        if review.get(key) != packet_value.get(key): errors.append(f"决策裂缝复检未绑定当前材料：{key}")
    covered = review.get("covered_checks")
    if not isinstance(covered, list) or any(check not in covered for check in REQUIRED_CHECKS): errors.append("决策裂缝复检覆盖不完整")
    evidence = review.get("evidence") if isinstance(review.get("evidence"), list) else []
    by_check = {str(item.get("check")): item for item in evidence if isinstance(item, dict)}
    for check in REQUIRED_CHECKS:
        item = by_check.get(check, {}); proof = str(item.get("proof") or "").strip(); explanation = str(item.get("explanation") or "").strip()
        if len(proof) < 10 or proof not in corpus or len(explanation) < 8: errors.append(f"决策裂缝复检证据不完整：{check}")
    if review.get("issues") != []: errors.append("决策裂缝复检仍有未解决问题")
    return list(dict.fromkeys(errors))


def seal(cache_root: Path, review_path: Path) -> Path:
    value = packet(cache_root); review = json.loads(review_path.read_text(encoding="utf-8")); errors = validate_review(value, review)
    if errors: raise ValueError("；".join(errors))
    output = cache_root / "decision-fissure-review.json"; output.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); return output


def verify(cache_root: Path) -> list[str]:
    try:
        value = packet(cache_root); path = cache_root / "decision-fissure-review.json"
        if not path.is_file(): return ["缺少决策裂缝当前有效回执"]
        return validate_review(value, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError) as error: return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("packet"); p.add_argument("cache_root", type=Path); p.add_argument("--output", type=Path)
    s = sub.add_parser("seal"); s.add_argument("cache_root", type=Path); s.add_argument("review", type=Path)
    v = sub.add_parser("verify"); v.add_argument("cache_root", type=Path); args = parser.parse_args()
    try:
        if args.command == "packet":
            text = json.dumps(packet(args.cache_root), ensure_ascii=False, indent=2) + "\n"
            if args.output: args.output.write_text(text, encoding="utf-8"); print(f"PASS: {args.output}")
            else: print(text, end="")
        elif args.command == "seal": print(f"PASS: {seal(args.cache_root, args.review)}")
        else:
            errors = verify(args.cache_root)
            if errors:
                for error in errors: print(f"FAIL: {error}")
                return 1
            print("PASS: decision fissure audit has a current review receipt")
    except (OSError, ValueError, json.JSONDecodeError) as error: print(f"FAIL: {error}"); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
