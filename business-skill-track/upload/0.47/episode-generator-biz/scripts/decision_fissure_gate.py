#!/usr/bin/env python3
"""Freeze and review the exhaustive pre-topology decision-fissure audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from mainline_story_gate import canonical, read_mainline, verify as verify_mainline
from build_stage_two_input import validate_frozen as validate_stage_two_input
from validate_mainline_projection import decomposition_issues


CONTRACT_VERSION = "nextplay.decision-fissure-audit.v2"
RECEIPT_VERSION = "nextplay.decision-fissure-review.v3"
ROOT_FIELDS = {"contract_version", "mainline_sha256", "core_goal", "core_goal_source_proof", "fissures"}
FISSURE_FIELDS = {"fissure_id", "mainline_position_proof", "decision_question", "actions", "disposition", "disposition_reason"}
ACTION_FIELDS = {"action_id", "action_text", "immediate_consequence", "core_goal_status", "route_ended", "ending_scope", "ending_reason", "goal_status_explanation"}
GOAL_STATES = {"continuing", "achieved", "failed", "abandoned", "unreachable"}
ENDING_SCOPES = {"none", "main", "minor"}
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
    decomposition_errors, _, _ = decomposition_issues(cache_root)
    if decomposition_errors:
        raise ValueError("主线分解未通过：" + "；".join(decomposition_errors))
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
    stage_two = validate_stage_two_input(cache_root)
    frozen_goal = str((stage_two.get("story") or {}).get("core_goal") or "").strip()
    core_goal = str(data.get("core_goal") or "").strip()
    goal_proof = str(data.get("core_goal_source_proof") or "").strip()
    if len(core_goal) < 12 or core_goal != frozen_goal or len(goal_proof) < 12 or goal_proof not in story:
        raise ValueError("决策裂缝审计没有逐字冻结核心目标及主线证据")
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
            ending_scope = action.get("ending_scope")
            reason = str(action.get("ending_reason") or "").strip()
            goal_explanation = str(action.get("goal_status_explanation") or "").strip()
            if not action_id or action_id in action_ids or len(action_text) < 2 or action_text in action_texts:
                raise ValueError(f"候选动作编号或文字非法：{fissure_id}/{action_id}")
            if len(consequence) < 10 or consequence in consequences or state not in GOAL_STATES or not isinstance(route_ended, bool):
                raise ValueError(f"候选动作后果或目标状态非法：{fissure_id}/{action_id}")
            if route_ended != (state != "continuing"):
                raise ValueError(f"路线结束判断与核心目标状态矛盾：{fissure_id}/{action_id}")
            if ending_scope not in ENDING_SCOPES or (route_ended and ending_scope == "none") or (not route_ended and ending_scope != "none"):
                raise ValueError(f"路线结束范围错误：{fissure_id}/{action_id}")
            loss_markers = ("永久丢失", "永久不可", "无法取得", "不能取得", "只剩", "擦除", "销毁")
            if state == "continuing" and "完整" in core_goal and any(marker in consequence for marker in loss_markers):
                raise ValueError(f"即时后果已使冻结核心目标中的完整成果不可达，不得改判为继续：{fissure_id}/{action_id}")
            if route_ended and len(reason) < 12:
                raise ValueError(f"结束动作缺少因果充分理由：{fissure_id}/{action_id}")
            if len(goal_explanation) < 12 or core_goal not in goal_explanation:
                raise ValueError(f"动作没有对照冻结核心目标判断状态：{fissure_id}/{action_id}")
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
    minor_actions = [
        (str(fissure.get("fissure_id") or ""), action)
        for fissure in fissures
        if fissure.get("disposition") == "adopt"
        for action in fissure.get("actions", [])
        if action.get("route_ended") is True and action.get("ending_scope") == "minor"
    ]
    if len(minor_actions) < 2:
        raise ValueError(f"初次拓扑至少需要2个独立小结局动作，实际{len(minor_actions)}")
    minor_fissures = {fissure_id for fissure_id, _ in minor_actions}
    if len(minor_fissures) < 2:
        raise ValueError("独立小结局必须从至少两个不同的真实决定裂缝自然产生，不得在同一裂缝内补数")
    story_terms = ("交易", "交换", "要求", "命令", "停止追查", "交出")
    if any(term in story for term in story_terms):
        compliant = False
        for fissure in fissures:
            proof = str(fissure.get("mainline_position_proof") or "")
            if not any(term in proof for term in story_terms):
                continue
            action_texts = [str(action.get("action_text") or "") for action in fissure["actions"]]
            has_refusal = any(any(term in text for term in ("拒绝", "不交", "继续追查")) for text in action_texts)
            has_literal_compliance = any(
                any(term in text for term in ("接受交易", "接受交换", "交出", "停止追查", "服从命令"))
                and "假意" not in text and "佯装" not in text
                for text in action_texts
            )
            if has_refusal and has_literal_compliance:
                compliant = True
                break
        if not compliant:
            raise ValueError("主线含明确交易/命令，但审计未同时覆盖字面服从与拒绝动作；假意服从不能替代真实接受")
    return path, data


def packet(cache_root: Path) -> dict[str, Any]:
    path, audit = read_audit(cache_root)
    _, mainline = read_mainline(cache_root)
    _, _, decomposition = decomposition_issues(cache_root)
    return {
        "packet_version": RECEIPT_VERSION,
        "audit_path": str(path),
        "audit_sha256": digest(audit),
        "mainline_sha256": digest(mainline),
        "mainline_decomposition_sha256": digest(decomposition),
        "required_checks": REQUIRED_CHECKS,
        "mainline": mainline,
        "mainline_decomposition": decomposition,
        "audit": audit,
    }


def validate_review(packet_value: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    corpus = "\n".join(
        all_text(packet_value[key])
        for key in ("mainline", "mainline_decomposition", "audit")
    )
    for key in ("audit_sha256", "mainline_sha256", "mainline_decomposition_sha256"):
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
