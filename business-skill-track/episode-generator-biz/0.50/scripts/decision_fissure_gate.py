#!/usr/bin/env python3
"""Freeze and review the exhaustive pre-topology decision-fissure audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from complete_story_gate import canonical, read_complete_story, verify as verify_complete_story


CONTRACT_VERSION = "nextplay.decision-fissure-audit.v3"
RECEIPT_VERSION = "nextplay.decision-fissure-review.v2"
ROOT_FIELDS = {"contract_version", "complete_story_sha256", "core_goal", "core_goal_source_proof", "fissures"}
FISSURE_FIELDS = {"fissure_id", "mainline_position_proof", "decision_question", "actions", "disposition", "disposition_reason"}
ACTION_FIELDS = {"action_id", "action_text", "immediate_consequence", "core_goal_status", "route_ended", "ending_scope", "ending_reason", "goal_status_explanation"}
GOAL_STATES = {"continuing", "achieved", "failed", "abandoned", "unreachable"}
ENDING_SCOPES = {"none", "small"}
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
    errors = verify_complete_story(cache_root)
    if errors:
        raise ValueError("冻结主线未通过：" + "；".join(errors))
    _, complete_story = read_complete_story(cache_root)
    story = str(complete_story["complete_story"])
    path = cache_root / "decision-fissure-audit.json"
    if not path.is_file():
        raise ValueError("缺少决策裂缝审计：decision-fissure-audit.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        raise ValueError("决策裂缝审计根字段错误")
    if data.get("contract_version") != CONTRACT_VERSION or data.get("complete_story_sha256") != digest(complete_story):
        raise ValueError("决策裂缝审计合同或完整故事绑定错误")
    core_goal = str(data.get("core_goal") or "").strip()
    goal_proof = str(data.get("core_goal_source_proof") or "").strip()
    if len(core_goal) < 12 or len(goal_proof) < 12 or goal_proof not in story:
        raise ValueError("决策裂缝审计没有从完整故事归纳核心目标并提供逐字证据")
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
            if ending_scope not in ENDING_SCOPES or (route_ended and ending_scope == "none") or (not route_ended and ending_scope != "none"):
                raise ValueError(f"路线结束范围错误：{fissure_id}/{action_id}")
            if route_ended and (state not in {"abandoned", "unreachable"} or ending_scope != "small"):
                raise ValueError(f"裂缝审计中的提前结束只能是离开核心故事的小结局：{fissure_id}/{action_id}")
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
    small_actions = [
        action
        for fissure in fissures
        if fissure.get("disposition") == "adopt"
        for action in fissure.get("actions", [])
        if action.get("route_ended") is True and action.get("ending_scope") == "small"
    ]
    if not small_actions:
        raise ValueError("初次拓扑至少需要一个由故事线自然产生的小结局动作")
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
    _, complete_story = read_complete_story(cache_root)
    return {"packet_version": RECEIPT_VERSION, "audit_path": str(path), "audit_sha256": digest(audit), "complete_story_sha256": digest(complete_story), "required_checks": REQUIRED_CHECKS, "complete_story": complete_story, "audit": audit}


def validate_review(packet_value: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    corpus = all_text(packet_value["complete_story"]) + "\n" + all_text(packet_value["audit"])
    for key in ("audit_sha256", "complete_story_sha256"):
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
