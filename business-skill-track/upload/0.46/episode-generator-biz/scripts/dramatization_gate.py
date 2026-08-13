#!/usr/bin/env python3
"""Validate synopsis-to-scene plans and bind their completed enactment to each script."""

from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from episode_artifact import section, subsection
from synopsis_set_gate import verify as verify_synopsis_set


CONTRACT_VERSION = "nextplay.episode-dramatization.v2"
RECEIPT_VERSION = "nextplay.episode-dramatization-review.v2"
PLAN_DIR = "dramatization-plans"
REVIEW_DIR = "dramatization-receipts"
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
LONG_SYNOPSIS_CHARS = 100
PROCESS_FIELDS = {
    "process_id", "scene", "actor", "trigger_or_basis", "action",
    "object", "resistance_or_verification", "result",
}
ABSTRACT_PROCESS_OBJECTS = {
    "无实物对象", "现场空间", "公开信息", "人物关系", "时间压力",
    "经营权限", "投资承诺", "安全风险", "资金状态",
}
EXTERNAL_AGENCY_PATTERNS = (
    r"银行(?:人员)?", r"警方", r"法院", r"消防(?:人员)?", r"保安",
    r"工作人员", r"员工", r"客户", r"新人",
)
GENERIC_EXPLANATION_PATTERNS = (
    r"两次可见行动",
    r"推进到.{0,8}(?:冻结|梗概|本集)结果",
    r"人物.{0,8}(?:采取|完成).{0,8}行动",
)
AUTHOR_SUMMARY_PATTERNS = (
    r"(?:他|她|二人|两人|众人).{0,10}目标是",
    r"(?:二人|两人|他们|众人).{0,12}必须.{0,8}(?:决定|选择)",
    r"这意味着",
    r"此举.{0,12}(?:让|使|导致)",
    r"由此进入",
    r"最终进入",
    r"为后续.{0,12}(?:留下|建立|提供)",
    r"具备.{0,12}(?:基础|条件|可能)",
    r"在.{0,16}之间选择",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalized(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE)


def is_dialogue_line(value: str) -> bool:
    return re.match(r"^[^：\n]{1,20}：", value.strip()) is not None


def narration_blocks(script: str) -> list[str]:
    blocks: list[str] = []
    for raw in re.split(r"\n\s*\n", script):
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        narration = [
            line for line in lines
            if not line.startswith("【") and not is_dialogue_line(line)
        ]
        text = "".join(narration).strip()
        if text:
            blocks.append(text)
    return blocks


def ngram_coverage(source: str, candidate: str, size: int = 4) -> float:
    if len(source) < size:
        return 0.0
    source_grams = {source[index:index + size] for index in range(len(source) - size + 1)}
    candidate_grams = {candidate[index:index + size] for index in range(len(candidate) - size + 1)}
    if not source_grams:
        return 0.0
    return len(source_grams & candidate_grams) / len(source_grams)


def character_coverage(source: str, candidate: str) -> float:
    if not source:
        return 0.0
    overlap = sum((Counter(source) & Counter(candidate)).values())
    return overlap / len(source)


def near_copy_passages(plan: dict[str, Any], script: str) -> list[str]:
    blocks = narration_blocks(script)
    windows: list[str] = []
    for start in range(len(blocks)):
        for width in range(1, min(3, len(blocks) - start) + 1):
            windows.append("".join(blocks[start:start + width]))
    hits: list[str] = []
    for beat in plan.get("beats") or []:
        if beat.get("mode") != "enact":
            continue
        source = normalized(str(beat.get("synopsis_source") or ""))
        if len(source) < 24:
            continue
        for window in windows:
            candidate = normalized(window)
            if not candidate:
                continue
            length_ratio = len(candidate) / len(source)
            if not 0.6 <= length_ratio <= 1.8:
                continue
            sequence_ratio = SequenceMatcher(None, source, candidate, autojunk=False).ratio()
            coverage = ngram_coverage(source, candidate)
            character_ratio = character_coverage(source, candidate)
            if (
                sequence_ratio >= 0.78
                or (sequence_ratio >= 0.68 and coverage >= 0.82)
                or (length_ratio <= 1.5 and character_ratio >= 0.82)
            ):
                hits.append(str(beat.get("beat_id") or "?"))
                break
    return list(dict.fromkeys(hits))


def author_summary_passages(script: str) -> list[str]:
    hits: list[str] = []
    for block in narration_blocks(script):
        if any(re.search(pattern, block) for pattern in AUTHOR_SUMMARY_PATTERNS):
            hits.append(block[:48])
    return hits


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
    expected_fields = {"contract_version", "episode_id", "synopsis_sha256", "story_treatment_sha256", "beats"}
    if set(plan) != expected_fields:
        errors.append(f"场面展开计划根字段错误：{episode_id}")
    if plan.get("contract_version") != CONTRACT_VERSION or plan.get("episode_id") != episode_id:
        errors.append(f"场面展开计划合同或编号错误：{episode_id}")
    synopsis_text = str(synopsis.get("synopsis") or "").strip()
    if any(re.search(pattern, synopsis_text) for pattern in CONDITIONAL_ROUTE_PATTERNS):
        errors.append(f"冻结梗概含条件式代写，必须退回阶段二：{episode_id}")
    if plan.get("synopsis_sha256") != sha256_text(canonical(synopsis)):
        errors.append(f"场面展开计划未绑定当前冻结梗概：{episode_id}")
    if plan.get("story_treatment_sha256") != sha256_text(canonical(treatment)):
        errors.append(f"场面展开计划未绑定当前完整故事：{episode_id}")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not beats:
        errors.append(f"场面展开计划缺少事件：{episode_id}")
        beats = []
    beat_fields = {"beat_id", "synopsis_source", "story_source_proof", "mode", "dramatic_goal", "start_state", "process_chain", "end_state", "state_changes"}
    assets = read_json(cache_root / "asset-catalog.json", "资产目录")
    allowed_actors = set(assets.get("characters") or []) | {"环境"}
    allowed_scenes = set(assets.get("scenes") or [])
    allowed_objects = set(assets.get("props") or []) | ABSTRACT_PROCESS_OBJECTS
    sources: list[str] = []
    total_processes = 0
    seen_ids: set[str] = set()
    cursor = 0
    for index, beat in enumerate(beats, 1):
        if not isinstance(beat, dict) or set(beat) != beat_fields:
            errors.append(f"事件字段错误：{episode_id}/B{index:02d}")
            continue
        beat_id = str(beat.get("beat_id") or "").strip()
        source = str(beat.get("synopsis_source") or "").strip()
        proof = str(beat.get("story_source_proof") or "").strip()
        mode = str(beat.get("mode") or "")
        goal = str(beat.get("dramatic_goal") or "").strip()
        start = str(beat.get("start_state") or "").strip()
        end = str(beat.get("end_state") or "").strip()
        processes = beat.get("process_chain")
        changes = beat.get("state_changes")
        if not re.fullmatch(r"B\d{2}", beat_id) or beat_id in seen_ids:
            errors.append(f"事件编号非法或重复：{episode_id}/{beat_id}")
        seen_ids.add(beat_id)
        location = synopsis_text.find(source, cursor) if source else -1
        if location < 0:
            errors.append(f"事件来源未按顺序逐字取自梗概：{episode_id}/{beat_id}")
        else:
            cursor = location + len(source)
        sources.append(source)
        if len(proof) < 8 or proof not in treatment_corpus:
            errors.append(f"完整故事证据无效：{episode_id}/{beat_id}")
        if mode not in MODES:
            errors.append(f"事件模式非法：{episode_id}/{beat_id}")
        if len(goal) < 8 or len(start) < 4 or len(end) < 4:
            errors.append(f"事件缺少目标或起止状态：{episode_id}/{beat_id}")
        if not isinstance(processes, list):
            errors.append(f"事件缺少过程链：{episode_id}/{beat_id}")
            processes = []
        if mode == "enact" and len(processes) < 2:
            errors.append(f"关键事件至少需要两个连续过程：{episode_id}/{beat_id}")
        process_ids: set[str] = set()
        for process_index, process in enumerate(processes, 1):
            total_processes += 1
            if not isinstance(process, dict) or set(process) != PROCESS_FIELDS:
                errors.append(f"过程链字段错误：{episode_id}/{beat_id}/P{process_index:02d}")
                continue
            process_id = str(process.get("process_id") or "").strip()
            scene = str(process.get("scene") or "").strip()
            actor = str(process.get("actor") or "").strip()
            obj = str(process.get("object") or "").strip()
            if not re.fullmatch(r"P\d{2}", process_id) or process_id in process_ids:
                errors.append(f"过程编号非法或重复：{episode_id}/{beat_id}/{process_id}")
            process_ids.add(process_id)
            if scene not in allowed_scenes:
                errors.append(f"过程使用未冻结场景：{episode_id}/{beat_id}/{process_id}/{scene}")
            if actor not in allowed_actors:
                errors.append(f"过程执行者不是冻结角色或环境：{episode_id}/{beat_id}/{process_id}/{actor}")
            if obj not in allowed_objects:
                errors.append(f"过程对象不是冻结道具或允许状态：{episode_id}/{beat_id}/{process_id}/{obj}")
            for field in ("trigger_or_basis", "action", "resistance_or_verification", "result"):
                if len(str(process.get(field) or "").strip()) < 8:
                    errors.append(f"过程缺少具体{field}：{episode_id}/{beat_id}/{process_id}")
            agency_text = str(process.get("action") or "") + str(process.get("result") or "")
            if actor != "环境" and any(re.search(pattern, agency_text) for pattern in EXTERNAL_AGENCY_PATTERNS):
                errors.append(f"过程把关键行动交给未登记执行者：{episode_id}/{beat_id}/{process_id}")
        if not isinstance(changes, list) or not changes or any(change not in STATE_CHANGES for change in changes):
            errors.append(f"状态变化类型非法：{episode_id}/{beat_id}")
        if mode == "enact" and normalized(start) == normalized(end):
            errors.append(f"关键事件必须产生真实状态变化：{episode_id}/{beat_id}")
    if normalized("".join(sources)) != normalized(synopsis_text):
        errors.append(f"事件集合未完整且无重复地覆盖冻结梗概：{episode_id}")
    if len(normalized(synopsis_text)) >= LONG_SYNOPSIS_CHARS and total_processes < 4:
        errors.append(f"较长事件至少需要四个连续过程，不能只保留原因和结果：{episode_id}")
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
    automatic_findings: list[str] = []
    if copied:
        automatic_findings.append("关键梗概原句被直接粘入剧本，尚未展开成戏：" + "、".join(copied))
    near_copied = near_copy_passages(plan, script)
    if near_copied:
        automatic_findings.append("关键梗概被近似搬入叙述，必须补出演出过程：" + "、".join(near_copied))
    summaries = author_summary_passages(script)
    if summaries:
        automatic_findings.append("正文出现作者摘要，必须改成动作、回应与现场后果：" + "｜".join(summaries))
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
        "automatic_findings": automatic_findings,
        "reference": reference,
        "synopsis": synopsis["synopsis"],
        "plan": plan,
        "script": script,
    }


def validate_review(packet: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if packet.get("automatic_findings"):
        errors.append("场面展开自动检查仍有未解决问题")
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
    used_process_proofs: set[str] = set()
    for beat in packet["plan"]["beats"]:
        beat_id = str(beat["beat_id"])
        check = by_id.get(beat_id) or {}
        if check.get("mode") != beat["mode"]:
            errors.append(f"场面展开复检模式不一致：{beat_id}")
        process_checks = check.get("process_checks")
        if not isinstance(process_checks, list):
            process_checks = []
            errors.append(f"场面展开复检缺少过程链证据：{beat_id}")
        by_process = {
            str(item.get("process_id")): item
            for item in process_checks if isinstance(item, dict)
        }
        cursor = 0
        for process in beat["process_chain"]:
            process_id = str(process["process_id"])
            process_check = by_process.get(process_id) or {}
            proofs = [
                str(process_check.get("action_proof") or "").strip(),
                str(process_check.get("resistance_or_verification_proof") or "").strip(),
                str(process_check.get("result_proof") or "").strip(),
            ]
            if len(set(proofs)) != 3:
                errors.append(f"过程的行动、阻力核验和结果必须分别举证：{beat_id}/{process_id}")
            for proof_index, proof_text in enumerate(proofs, 1):
                location = script.find(proof_text, cursor)
                if len(proof_text) < 4 or location < 0:
                    errors.append(f"过程未在正文中按序演出：{beat_id}/{process_id}/{proof_index}")
                else:
                    cursor = location + len(proof_text)
                if proof_text in used_process_proofs:
                    errors.append(f"不同过程不得复用同一正文证据：{beat_id}/{process_id}/{proof_index}")
                if proof_text:
                    used_process_proofs.add(proof_text)
        if set(by_process) != {str(process["process_id"]) for process in beat["process_chain"]}:
            errors.append(f"过程复检集合与计划不一致：{beat_id}")
        end_proof = str(check.get("end_state_proof") or "").strip()
        explanation = str(check.get("state_change_explanation") or "").strip()
        end_location = script.find(end_proof, cursor) if end_proof else -1
        if len(end_proof) < 4 or end_location < 0:
            errors.append(f"场面展开缺少结果证据：{beat_id}")
        if beat["mode"] == "enact" and len(explanation) < 8:
            errors.append(f"场面展开缺少状态变化说明：{beat_id}")
        elif beat["mode"] == "enact" and any(
            re.search(pattern, explanation) for pattern in GENERIC_EXPLANATION_PATTERNS
        ):
            errors.append(f"场面展开状态变化说明过于通用：{beat_id}")
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
