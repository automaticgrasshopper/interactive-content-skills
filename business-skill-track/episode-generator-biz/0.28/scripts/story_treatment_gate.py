#!/usr/bin/env python3
"""Validate, packet, seal, and verify the private complete-story treatment."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from build_stage_two_input import validate_frozen as validate_stage_two_input
from validate_user_intent_lock import contract_binding


CONTRACT_VERSION = "nextplay.episode-story-treatment.v1"
RECEIPT_VERSION = "nextplay.episode-story-treatment-review.v2"
TREATMENT_NAME = "story-treatment.json"
RECEIPT_NAME = "story-treatment-review.json"
ROOT_FIELDS = {"contract_version", "title", "complete_story", "choices", "endings"}
COMPREHENSION_FIELDS = {
    "protagonist_goal": "主角目标",
    "causal_progression": "全篇因果推进",
    "branch_logic": "分支逻辑",
    "ending_payoffs": "结局回收",
}
REQUIRED_CHECKS = [
    "用户要求与上游事实",
    "人物动机与知情边界",
    "全篇因果连续",
    "分支即时差异与持续承接",
    "汇合共同事实",
    "结局因果回收",
    "类型期待正面兑现",
    "路线去向与情绪结算",
    "路线级拓扑先于节点分配",
    "信息吞吐与后段完整度",
]
FAILURE_MARKERS = ("无法判断", "无法确认", "信息不足", "未说明", "故事不清楚")
EPISODE_ID = re.compile(r"episode-\d{3}")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def all_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(all_text(item) for item in value)
    if isinstance(value, dict):
        return "\n".join(all_text(item) for item in value.values())
    return ""


def read_treatment(cache_root: Path) -> tuple[Path, dict[str, Any]]:
    path = cache_root / TREATMENT_NAME
    if not path.is_file():
        raise ValueError("缺少完整故事：story-treatment.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        raise ValueError("完整故事根字段错误")
    if data.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(f"完整故事合同错误：期望 {CONTRACT_VERSION}")
    if len(str(data.get("title") or "").strip()) < 2:
        raise ValueError("完整故事缺少标题")
    complete_story = str(data.get("complete_story") or "").strip()
    if len(complete_story) < 500:
        raise ValueError("完整故事过短，尚不足以承载从开场到全部结局的连续因果")
    if EPISODE_ID.search(all_text(data)):
        raise ValueError("路线级完整故事不得提前出现分集编号")

    choices = data.get("choices")
    endings = data.get("endings")
    if not isinstance(choices, list) or not isinstance(endings, list) or not endings:
        raise ValueError("完整故事的 choices/endings 必须为数组，且至少有一个结局")

    choice_ids: set[str] = set()
    questions: set[str] = set()
    for index, choice in enumerate(choices, 1):
        if not isinstance(choice, dict) or set(choice) != {
            "choice_id", "dramatic_cause", "question", "options", "merge_or_ending"
        }:
            raise ValueError(f"选择记录字段错误：第{index}项")
        choice_id = str(choice.get("choice_id") or "").strip()
        question = str(choice.get("question") or "").strip()
        if not choice_id.startswith("choice-") or choice_id in choice_ids:
            raise ValueError(f"选择编号非法或重复：{choice_id}")
        if len(question) < 4 or question in questions:
            raise ValueError(f"选择问题过短或重复：{choice_id}")
        choice_ids.add(choice_id)
        questions.add(question)
        for field in ("dramatic_cause", "merge_or_ending"):
            if len(str(choice.get(field) or "").strip()) < 10:
                raise ValueError(f"选择缺少可读的{field}：{choice_id}")
        options = choice.get("options")
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError(f"选择至少需要两个选项：{choice_id}")
        option_ids: set[str] = set()
        option_texts: set[str] = set()
        immediate: set[str] = set()
        lasting: set[str] = set()
        for option in options:
            if not isinstance(option, dict) or set(option) != {
                "option_id", "option_text", "immediate_consequence", "lasting_difference"
            }:
                raise ValueError(f"选项字段错误：{choice_id}")
            option_id = str(option.get("option_id") or "").strip()
            option_text = str(option.get("option_text") or "").strip()
            consequence = str(option.get("immediate_consequence") or "").strip()
            difference = str(option.get("lasting_difference") or "").strip()
            if not option_id or option_id in option_ids:
                raise ValueError(f"选项编号为空或重复：{choice_id}/{option_id}")
            if len(option_text) < 2 or option_text in option_texts:
                raise ValueError(f"选项文字过短或重复：{choice_id}/{option_id}")
            if len(consequence) < 8 or len(difference) < 8:
                raise ValueError(f"选项缺少即时后果或持续差异：{choice_id}/{option_id}")
            option_ids.add(option_id)
            option_texts.add(option_text)
            immediate.add(consequence)
            lasting.add(difference)
        if len(immediate) != len(options) or len(lasting) != len(options):
            raise ValueError(f"不同选项必须有不同的即时后果和持续差异：{choice_id}")

    ending_titles: set[str] = set()
    formal = failure = 0
    for ending in endings:
        if not isinstance(ending, dict) or set(ending) != {"title", "kind", "causal_payoff"}:
            raise ValueError("结局记录字段错误")
        title = str(ending.get("title") or "").strip()
        kind = ending.get("kind")
        if not title or title in ending_titles:
            raise ValueError(f"结局标题为空或重复：{title}")
        if kind not in {"formal", "failure"}:
            raise ValueError(f"结局类型非法：{title}")
        if len(str(ending.get("causal_payoff") or "").strip()) < 12:
            raise ValueError(f"结局缺少因果回收：{title}")
        ending_titles.add(title)
        formal += kind == "formal"
        failure += kind == "failure"

    basis_path = cache_root / "run-basis.json"
    if not basis_path.is_file():
        raise ValueError("完整故事门禁缺少已通过的 run-basis.json")
    basis = json.loads(basis_path.read_text(encoding="utf-8"))
    plan = basis.get("ending_plan") if isinstance(basis, dict) else None
    if not isinstance(plan, dict):
        raise ValueError("run-basis.json 缺少 ending_plan")
    if len(endings) != plan.get("total") or formal != plan.get("formal") or failure != plan.get("failure"):
        raise ValueError("完整故事结局数量与冻结运行基础不一致")
    return path, data


def packet(cache_root: Path) -> dict[str, Any]:
    path, treatment = read_treatment(cache_root)
    stage_two_input = validate_stage_two_input(cache_root)
    source_sha, contract_sha = contract_binding(cache_root)
    basis_path = cache_root / "run-basis.json"
    assets_path = cache_root / "asset-catalog.json"
    if not assets_path.is_file():
        raise ValueError("完整故事门禁缺少 asset-catalog.json")
    return {
        "packet_version": RECEIPT_VERSION,
        "treatment_path": str(path),
        "treatment_sha256": sha256_text(canonical(treatment)),
        "stage_two_input_sha256": sha256_text(canonical(stage_two_input)),
        "run_basis_sha256": sha256_text(basis_path.read_text(encoding="utf-8")),
        "asset_catalog_sha256": sha256_text(assets_path.read_text(encoding="utf-8")),
        "user_intent_source_sha256": source_sha,
        "user_intent_contract_sha256": contract_sha,
        "required_comprehension": COMPREHENSION_FIELDS,
        "required_checks": REQUIRED_CHECKS,
        "treatment": treatment,
    }


def validate_review(packet_value: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    corpus = all_text(packet_value["treatment"])
    comprehension = review.get("comprehension")
    if not isinstance(comprehension, dict):
        comprehension = {}
        errors.append("完整故事复检缺少结构化理解门")
    proofs: list[str] = []
    for key, label in COMPREHENSION_FIELDS.items():
        item = comprehension.get(key)
        if not isinstance(item, dict):
            errors.append(f"完整故事理解门缺少：{label}")
            continue
        answer = str(item.get("answer") or "").strip()
        proof = str(item.get("proof") or "").strip()
        if len(answer) < 8 or len(proof) < 12:
            errors.append(f"完整故事理解门证据不完整：{label}")
        elif proof not in corpus:
            errors.append(f"完整故事理解门证据不在当前故事中：{label}")
        elif any(marker in answer or marker in proof for marker in FAILURE_MARKERS):
            errors.append(f"完整故事理解门未通过：{label}")
        proofs.append(proof)
    if len([proof for proof in proofs if proof]) != len(set(proof for proof in proofs if proof)):
        errors.append("完整故事理解门不得重复使用同一证据")

    covered = review.get("covered_checks")
    if not isinstance(covered, list) or any(check not in covered for check in REQUIRED_CHECKS):
        errors.append("完整故事复检覆盖不完整")
    evidence = review.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
        errors.append("完整故事复检缺少逐项证据")
    by_check = {str(item.get("check")): item for item in evidence if isinstance(item, dict)}
    for check in REQUIRED_CHECKS:
        item = by_check.get(check) or {}
        proof = str(item.get("proof") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        if len(proof) < 10 or len(explanation) < 8:
            errors.append(f"完整故事复检证据不完整：{check}")
        elif proof not in corpus:
            errors.append(f"完整故事复检证据不在当前故事中：{check}")
    if review.get("issues") != []:
        errors.append("完整故事复检仍有未解决问题")
    for key in (
        "treatment_sha256", "stage_two_input_sha256", "run_basis_sha256", "asset_catalog_sha256",
        "user_intent_source_sha256", "user_intent_contract_sha256",
    ):
        if review.get(key) != packet_value.get(key):
            errors.append(f"完整故事复检未绑定当前材料：{key}")
    return list(dict.fromkeys(errors))


def seal(cache_root: Path, review_path: Path) -> Path:
    packet_value = packet(cache_root)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    errors = validate_review(packet_value, review)
    if errors:
        raise ValueError("；".join(errors))
    receipt = {
        "packet_version": packet_value["packet_version"],
        "treatment_sha256": packet_value["treatment_sha256"],
        "stage_two_input_sha256": packet_value["stage_two_input_sha256"],
        "run_basis_sha256": packet_value["run_basis_sha256"],
        "asset_catalog_sha256": packet_value["asset_catalog_sha256"],
        "user_intent_source_sha256": packet_value["user_intent_source_sha256"],
        "user_intent_contract_sha256": packet_value["user_intent_contract_sha256"],
        "comprehension": review["comprehension"],
        "covered_checks": review["covered_checks"],
        "evidence": review["evidence"],
        "issues": [],
    }
    output = cache_root / RECEIPT_NAME
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def verify(cache_root: Path) -> list[str]:
    try:
        packet_value = packet(cache_root)
        path = cache_root / RECEIPT_NAME
        if not path.is_file():
            return ["缺少完整故事当前有效回执"]
        receipt = json.loads(path.read_text(encoding="utf-8"))
        return validate_review(packet_value, receipt)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    packet_parser = subparsers.add_parser("packet")
    packet_parser.add_argument("cache_root", type=Path)
    packet_parser.add_argument("--output", type=Path)
    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("cache_root", type=Path)
    seal_parser.add_argument("review", type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "packet":
            value = json.dumps(packet(args.cache_root), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(value, encoding="utf-8")
                print(f"PASS: {args.output}")
            else:
                print(value, end="")
        elif args.command == "seal":
            print(f"PASS: {seal(args.cache_root, args.review)}")
        else:
            errors = verify(args.cache_root)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}")
                return 1
            print("PASS: complete interactive story has a current review receipt")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
