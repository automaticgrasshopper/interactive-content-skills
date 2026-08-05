#!/usr/bin/env python3
"""Validate synopsis-to-scene plans and bind their completed enactment to each script."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from episode_artifact import section, subsection
from synopsis_set_gate import verify as verify_synopsis_set


CONTRACT_VERSION = "nextplay.episode-dramatization.v1"
RECEIPT_VERSION = "nextplay.episode-dramatization-review.v1"
PLAN_DIR = "dramatization-plans"
REVIEW_DIR = "dramatization-reviews"
REFERENCE_NAME = "dramatization-completion.md"
SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = SKILL_ROOT / "references" / REFERENCE_NAME
MANIFEST_PATH = SKILL_ROOT / "reference-manifest.json"
MODES = {"setup", "enact"}
STATE_CHANGES = {
    "position", "possession", "access", "attention", "knowledge",
    "risk", "commitment", "time-pressure", "relationship",
}
REQUIRED_CHECKS = [
    "梗概逐项覆盖",
    "关键事件现场化",
    "动作改变人物或现场状态",
    "没有用梗概旁白代替戏",
    "只演当前路线事实",
]
CONDITIONAL_ROUTE_PATTERNS = (
    r"若走.{0,12}路线",
    r"若是.{0,12}来路",
    r"两种来路",
    r"另一种情况下",
    r"视玩家此前选择",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalized(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE)


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少{label}：{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须为JSON对象")
    return value


def read_sources(cache_root: Path, episode_id: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    if not re.fullmatch(r"episode-\d{3}", episode_id):
        raise ValueError(f"非法分集编号：{episode_id}")
    synopsis = read_json(cache_root / "episode-synopses" / f"{episode_id}.json", "冻结梗概")
    if synopsis.get("episode_id") != episode_id:
        raise ValueError(f"冻结梗概编号不一致：{episode_id}")
    treatment = read_json(cache_root / "story-treatment.json", "完整故事")
    corpus = "\n".join(str(value) for value in treatment.values() if isinstance(value, str))
    corpus += "\n" + json.dumps(treatment.get("choices") or [], ensure_ascii=False)
    corpus += "\n" + json.dumps(treatment.get("endings") or [], ensure_ascii=False)
    return synopsis, treatment, corpus


def plan_path(cache_root: Path, episode_id: str) -> Path:
    return cache_root / PLAN_DIR / f"{episode_id}.json"


def receipt_path(cache_root: Path, episode_id: str) -> Path:
    return cache_root / REVIEW_DIR / f"{episode_id}.json"


def validate_plan(cache_root: Path, episode_id: str) -> tuple[dict[str, Any], list[str]]:
    errors = verify_synopsis_set(cache_root)
    synopsis, treatment, treatment_corpus = read_sources(cache_root, episode_id)
    plan = read_json(plan_path(cache_root, episode_id), "场面展开计划")
    expected_fields = {
        "contract_version", "episode_id", "synopsis_sha256",
        "story_treatment_sha256", "beats",
    }
    if set(plan) != expected_fields:
        errors.append(f"场面展开计划根字段错误：{episode_id}")
    if plan.get("contract_version") != CONTRACT_VERSION or plan.get("episode_id") != episode_id:
        errors.append(f"场面展开计划合同或编号错误：{episode_id}")
    synopsis_text = str(synopsis.get("synopsis") or "").strip()
    if any(re.search(pattern, synopsis_text) for pattern in CONDITIONAL_ROUTE_PATTERNS) or synopsis_text.count("优先来路") >= 2:
        errors.append(f"冻结梗概含条件式代写，必须退回阶段二拆成当前节点唯一事实：{episode_id}")
    if plan.get("synopsis_sha256") != sha256_text(canonical(synopsis)):
        errors.append(f"场面展开计划未绑定当前冻结梗概：{episode_id}")
    if plan.get("story_treatment_sha256") != sha256_text(canonical(treatment)):
        errors.append(f"场面展开计划未绑定当前完整故事：{episode_id}")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not beats:
        errors.append(f"场面展开计划缺少beats：{episode_id}")
        beats = []
    expected_beat_fields = {
        "beat_id", "synopsis_source", "story_source_proof", "mode",
        "start_state", "onscreen_steps", "end_state", "state_changes",
    }
    sources: list[str] = []
    seen_ids: set[str] = set()
    cursor = 0
    for index, beat in enumerate(beats, 1):
        if not isinstance(beat, dict) or set(beat) != expected_beat_fields:
            errors.append(f"场面展开拍字段错误：{episode_id}/B{index:02d}")
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        source = str(beat.get("synopsis_source") or "").strip()
        proof = str(beat.get("story_source_proof") or "").strip()
        mode = str(beat.get("mode") or "")
        start = str(beat.get("start_state") or "").strip()
        end = str(beat.get("end_state") or "").strip()
        steps = beat.get("onscreen_steps")
        changes = beat.get("state_changes")
        if not re.fullmatch(r"B\d{2}", beat_id) or beat_id in seen_ids:
            errors.append(f"场面展开拍编号非法或重复：{episode_id}/{beat_id}")
        seen_ids.add(beat_id)
        if not source:
            errors.append(f"场面展开拍缺少梗概原文：{episode_id}/{beat_id}")
        else:
            location = synopsis_text.find(source, cursor)
            if location < 0:
                errors.append(f"梗概原文未按顺序逐字取自当前梗概：{episode_id}/{beat_id}")
            else:
                cursor = location + len(source)
            sources.append(source)
        if len(proof) < 8 or proof not in treatment_corpus:
            errors.append(f"完整故事证据无效：{episode_id}/{beat_id}")
        if mode not in MODES:
            errors.append(f"场面展开模式非法：{episode_id}/{beat_id}")
        if len(start) < 4 or len(end) < 4:
            errors.append(f"场面展开缺少起止状态：{episode_id}/{beat_id}")
        if not isinstance(steps, list) or any(len(str(step).strip()) < 4 for step in steps):
            errors.append(f"场面展开缺少可见动作步骤：{episode_id}/{beat_id}")
            steps = []
        if mode == "enact" and len(steps) < 2:
            errors.append(f"关键事件至少需要两个连续可见步骤：{episode_id}/{beat_id}")
        if not isinstance(changes, list) or any(change not in STATE_CHANGES for change in changes):
            errors.append(f"状态变化类型非法：{episode_id}/{beat_id}")
            changes = []
        if mode == "enact" and (not changes or normalized(start) == normalized(end)):
            errors.append(f"关键事件必须产生真实状态变化：{episode_id}/{beat_id}")
    if normalized("".join(sources)) != normalized(synopsis_text):
        errors.append(f"场面展开拍未完整且无重复地覆盖冻结梗概：{episode_id}")
    return plan, list(dict.fromkeys(errors))


def read_script(cache_root: Path, episode_id: str) -> tuple[str, str]:
    path = cache_root / "episodes" / f"{episode_id}.md"
    if not path.is_file():
        raise ValueError(f"缺少分集正文：{episode_id}")
    artifact = path.read_text(encoding="utf-8").strip()
    match = re.search(r"^## 完整剧本\n\n(.*?)(?=^# 剧本分析)", artifact, re.MULTILINE | re.DOTALL)
    if not match or not match.group(1).strip():
        raise ValueError(f"分集缺少完整剧本正文：{episode_id}")
    return artifact, match.group(1).strip()


def current_reference() -> tuple[str, str, str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    names = (manifest.get("phases") or {}).get("dramatization-completion") or []
    if names != [REFERENCE_NAME]:
        raise ValueError("dramatization-completion阶段必须且只能装载场面展开复检reference")
    text = REFERENCE_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("场面展开复检reference为空")
    return str(manifest.get("skill_version") or ""), text, sha256_text(text)


def build_packet(cache_root: Path, episode_id: str) -> dict[str, Any]:
    plan, errors = validate_plan(cache_root, episode_id)
    if errors:
        raise ValueError("；".join(errors))
    artifact, script = read_script(cache_root, episode_id)
    synopsis, treatment, _ = read_sources(cache_root, episode_id)
    artifact_synopsis = subsection(section(artifact, "分集剧本"), "单集梗概")
    if artifact_synopsis != str(synopsis.get("synopsis") or "").strip():
        raise ValueError(f"正文中的梗概与冻结梗概不一致：{episode_id}")
    copied: list[str] = []
    for beat in plan["beats"]:
        source = str(beat["synopsis_source"]).strip()
        if beat["mode"] == "enact" and len(normalized(source)) >= 24 and source in script:
            copied.append(str(beat["beat_id"]))
    if copied:
        raise ValueError("关键梗概原句被直接粘入剧本，尚未展开成戏：" + "、".join(copied))
    version, reference, reference_sha = current_reference()
    return {
        "packet_version": RECEIPT_VERSION,
        "skill_version": version,
        "episode_id": episode_id,
        "plan_sha256": sha256_text(canonical(plan)),
        "script_sha256": sha256_text(artifact),
        "synopsis_sha256": sha256_text(canonical(synopsis)),
        "story_treatment_sha256": sha256_text(canonical(treatment)),
        "reference_name": REFERENCE_NAME,
        "reference_sha256": reference_sha,
        "required_checks": REQUIRED_CHECKS,
        "reference": reference,
        "synopsis": synopsis["synopsis"],
        "plan": plan,
        "script": script,
    }


def validate_review(packet: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("plan_sha256", "script_sha256", "synopsis_sha256", "story_treatment_sha256", "reference_sha256"):
        if review.get(key) != packet.get(key):
            errors.append(f"场面展开复检未绑定当前材料：{key}")
    covered = review.get("covered_checks")
    if not isinstance(covered, list) or any(check not in covered for check in REQUIRED_CHECKS):
        errors.append("场面展开复检覆盖不完整")
    if review.get("issues") != []:
        errors.append("场面展开复检仍有未解决问题")
    beat_checks = review.get("beat_checks")
    if not isinstance(beat_checks, list):
        beat_checks = []
        errors.append("场面展开复检缺少逐拍证据")
    by_id = {str(item.get("beat_id")): item for item in beat_checks if isinstance(item, dict)}
    if len(by_id) != len(beat_checks):
        errors.append("场面展开复检拍编号重复或缺失")
    script = str(packet["script"])
    for beat in packet["plan"]["beats"]:
        beat_id = str(beat["beat_id"])
        check = by_id.get(beat_id) or {}
        if check.get("mode") != beat["mode"]:
            errors.append(f"场面展开复检模式不一致：{beat_id}")
        proofs = check.get("step_proofs")
        if not isinstance(proofs, list) or len(proofs) != len(beat["onscreen_steps"]):
            errors.append(f"场面展开步骤证据数量错误：{beat_id}")
            proofs = []
        cursor = 0
        for index, proof in enumerate(proofs):
            proof_text = str(proof).strip()
            location = script.find(proof_text, cursor)
            if len(proof_text) < 4 or location < 0:
                errors.append(f"场面展开步骤未在正文中按序演出：{beat_id}/{index + 1}")
            else:
                cursor = location + len(proof_text)
        end_proof = str(check.get("end_state_proof") or "").strip()
        explanation = str(check.get("state_change_explanation") or "").strip()
        if len(end_proof) < 4 or end_proof not in script:
            errors.append(f"场面展开缺少结果证据：{beat_id}")
        if beat["mode"] == "enact" and len(explanation) < 8:
            errors.append(f"场面展开缺少状态变化说明：{beat_id}")
    if set(by_id) != {str(beat["beat_id"]) for beat in packet["plan"]["beats"]}:
        errors.append("场面展开复检拍集合与计划不一致")
    return list(dict.fromkeys(errors))


def seal(cache_root: Path, episode_id: str, review_path: Path) -> Path:
    packet = build_packet(cache_root, episode_id)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    errors = validate_review(packet, review)
    if errors:
        raise ValueError("；".join(errors))
    receipt = {
        "packet_version": packet["packet_version"],
        "skill_version": packet["skill_version"],
        "episode_id": episode_id,
        "plan_sha256": packet["plan_sha256"],
        "script_sha256": packet["script_sha256"],
        "synopsis_sha256": packet["synopsis_sha256"],
        "story_treatment_sha256": packet["story_treatment_sha256"],
        "reference_name": packet["reference_name"],
        "reference_sha256": packet["reference_sha256"],
        "required_checks": REQUIRED_CHECKS,
        "covered_checks": review["covered_checks"],
        "beat_checks": review["beat_checks"],
        "issues": [],
    }
    output = receipt_path(cache_root, episode_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def verify_one(cache_root: Path, episode_id: str) -> list[str]:
    try:
        packet = build_packet(cache_root, episode_id)
        receipt = read_json(receipt_path(cache_root, episode_id), "场面展开复检回执")
        errors: list[str] = []
        for key in (
            "packet_version", "episode_id", "plan_sha256", "script_sha256",
            "synopsis_sha256", "story_treatment_sha256", "reference_name",
            "reference_sha256", "required_checks",
        ):
            if receipt.get(key) != packet.get(key):
                errors.append(f"场面展开复检回执已失效：{episode_id}/{key}")
        errors.extend(validate_review(packet, receipt))
        return list(dict.fromkeys(errors))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def verify_project(cache_root: Path) -> list[str]:
    errors: list[str] = []
    episode_ids = sorted(path.stem for path in (cache_root / "episodes").glob("episode-*.md"))
    if not episode_ids:
        return ["没有可验证的分集正文"]
    for episode_id in episode_ids:
        errors.extend(verify_one(cache_root, episode_id))
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("cache_root", type=Path)
    plan_parser.add_argument("episode_id")
    packet_parser = subparsers.add_parser("packet")
    packet_parser.add_argument("cache_root", type=Path)
    packet_parser.add_argument("episode_id")
    packet_parser.add_argument("--output", type=Path)
    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("cache_root", type=Path)
    seal_parser.add_argument("episode_id")
    seal_parser.add_argument("review", type=Path)
    verify_one_parser = subparsers.add_parser("verify-one")
    verify_one_parser.add_argument("cache_root", type=Path)
    verify_one_parser.add_argument("episode_id")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            _, errors = validate_plan(args.cache_root, args.episode_id)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}")
                return 1
            print(f"PASS: {args.episode_id} has a complete synopsis-to-scene plan")
        elif args.command == "packet":
            value = json.dumps(build_packet(args.cache_root, args.episode_id), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(value, encoding="utf-8")
                print(f"PASS: {args.output}")
            else:
                print(value, end="")
        elif args.command == "seal":
            print(f"PASS: {seal(args.cache_root, args.episode_id, args.review)}")
        elif args.command == "verify-one":
            errors = verify_one(args.cache_root, args.episode_id)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}")
                return 1
            print(f"PASS: {args.episode_id} has a current dramatization receipt")
        else:
            errors = verify_project(args.cache_root)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}")
                return 1
            print("PASS: every episode has a current dramatization receipt")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
