#!/usr/bin/env python3
"""Prepare and verify mandatory per-episode quality-review receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from validate_user_intent_lock import contract_binding
from validate_topology import parse
from episode_artifact import predecessors, section, subsection


SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_NAME = "episode-quality-review.md"
REFERENCE_PATH = SKILL_ROOT / "references" / REFERENCE_NAME
MANIFEST_PATH = SKILL_ROOT / "reference-manifest.json"
REVIEW_DIR = "quality-reviews"
SYNOPSIS_DIR = "episode-synopses"
SYNOPSIS_REVIEW_DIR = "synopsis-reviews"
SYNOPSIS_VERSION = "nextplay.episode-synopsis.v1"
SYNOPSIS_PACKET_VERSION = "episode-synopsis-gate-v1"
PLAIN_LANGUAGE_CHECK = "普通话表达与叙述可读"
SYNOPSIS_ALIGNMENT_CHECK = "梗概与正文一致"
REQUIRED_CHECKS = [
    "事实来源与知情",
    "首次出现与必要交代",
    "因果相邻与可见后果",
    "话茬与现场目的",
    "口语组织与反过度压缩",
    PLAIN_LANGUAGE_CHECK,
    SYNOPSIS_ALIGNMENT_CHECK,
    "结尾画面与下一入口",
]
COMPREHENSION_FIELDS = {
    "character_task": "人物任务",
    "trigger_cost": "触发代价",
    "action_result": "行动结果",
    "next_entry": "下一入口",
}
COMPREHENSION_FAILURE_MARKERS = ("正文不清楚", "无法判断", "无法确认", "信息不足", "未说明")
SYNOPSIS_COMPREHENSION_FIELDS = {
    "character_task": "人物与当前问题",
    "episode_change": "本集实际变化",
    "next_entry": "本集结束后的具体去向",
}


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_episode(cache_root: Path, episode_id: str) -> tuple[Path, str]:
    if not re.fullmatch(r"episode-\d{3}", episode_id):
        raise ValueError(f"非法分集编号：{episode_id}")
    path = cache_root / "episodes" / f"{episode_id}.md"
    if not path.is_file():
        raise ValueError(f"缺少分集正文：{episode_id}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"分集正文为空：{episode_id}")
    return path, text


def complete_script(artifact: str) -> str:
    match = re.search(
        r"^## 完整剧本\n\n(.*?)(?=^# 剧本分析)",
        artifact,
        re.MULTILINE | re.DOTALL,
    )
    if not match or not match.group(1).strip():
        raise ValueError("分集缺少完整剧本正文")
    return match.group(1).strip()


def synopsis_path(cache_root: Path, episode_id: str) -> Path:
    return cache_root / SYNOPSIS_DIR / f"{episode_id}.json"


def synopsis_receipt_path(cache_root: Path, episode_id: str) -> Path:
    return cache_root / SYNOPSIS_REVIEW_DIR / f"{episode_id}.json"


def read_synopsis(cache_root: Path, episode_id: str) -> tuple[Path, dict[str, Any]]:
    path = synopsis_path(cache_root, episode_id)
    if not path.is_file():
        raise ValueError(f"缺少单集梗概草案：{episode_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "contract_version", "episode_id", "title", "synopsis", "conflict",
        "predecessors", "successors",
    }
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError(f"单集梗概草案字段错误：{episode_id}")
    if data.get("contract_version") != SYNOPSIS_VERSION or data.get("episode_id") != episode_id:
        raise ValueError(f"单集梗概草案合同或编号错误：{episode_id}")
    for key in ("title", "synopsis", "conflict"):
        if len(str(data.get(key) or "").strip()) < 6:
            raise ValueError(f"单集梗概草案缺少可读内容：{episode_id}/{key}")
    for key in ("predecessors", "successors"):
        value = data.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"单集梗概草案节点列表错误：{episode_id}/{key}")
    nodes = parse(cache_root / "topology.md")
    if episode_id not in nodes:
        raise ValueError(f"冻结拓扑不存在分集：{episode_id}")
    expected_predecessors = predecessors(nodes)[episode_id]
    if data["title"].strip() != str(nodes[episode_id]["title"]):
        raise ValueError(f"单集梗概标题与冻结拓扑不一致：{episode_id}")
    if data["predecessors"] != expected_predecessors:
        raise ValueError(f"单集梗概前置节点与冻结拓扑不一致：{episode_id}")
    if data["successors"] != list(nodes[episode_id]["successors"]):
        raise ValueError(f"单集梗概后续节点与冻结拓扑不一致：{episode_id}")
    return path, data


def synopsis_packet(cache_root: Path, episode_id: str) -> dict[str, Any]:
    if (cache_root / "episodes" / f"{episode_id}.md").exists():
        raise ValueError(f"梗概理解门通过前不得写完整剧本：{episode_id}")
    _assert_no_unsealed_work(cache_root, episode_id, synopsis_phase=True)
    _assert_predecessors_sealed(cache_root, episode_id)
    path, data = read_synopsis(cache_root, episode_id)
    user_source_sha, user_contract_sha = contract_binding(cache_root)
    return {
        "packet_version": SYNOPSIS_PACKET_VERSION,
        "skill_version": current_reference()[0],
        "episode_id": episode_id,
        "synopsis_path": str(path),
        "synopsis_sha256": sha256(path.read_text(encoding="utf-8").strip()),
        "user_intent_source_sha256": user_source_sha,
        "user_intent_contract_sha256": user_contract_sha,
        "required_comprehension": SYNOPSIS_COMPREHENSION_FIELDS,
        "title": data["title"],
        "synopsis": data["synopsis"],
        "conflict": data["conflict"],
        "predecessors": data["predecessors"],
        "successors": data["successors"],
    }


def validate_synopsis_review(packet: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    comprehension = review.get("comprehension")
    if not isinstance(comprehension, dict):
        comprehension = {}
        errors.append("梗概复检缺少结构化理解门")
    synopsis = str(packet["synopsis"])
    for key, label in SYNOPSIS_COMPREHENSION_FIELDS.items():
        item = comprehension.get(key)
        if not isinstance(item, dict):
            errors.append(f"梗概理解门缺少：{label}")
            continue
        answer = str(item.get("answer") or "").strip()
        proof = str(item.get("proof") or "").strip()
        if len(answer) < 4 or len(proof) < 6:
            errors.append(f"梗概理解门证据不完整：{label}")
        elif proof not in synopsis:
            errors.append(f"梗概理解门证据不在单集梗概中：{label}")
        elif any(marker in answer or marker in proof for marker in COMPREHENSION_FAILURE_MARKERS):
            errors.append(f"梗概理解门未通过：{label}")
    if review.get("issues") != []:
        errors.append("梗概复检仍有未解决问题")
    for key in (
        "synopsis_sha256", "user_intent_source_sha256",
        "user_intent_contract_sha256",
    ):
        if review.get(key) != packet.get(key):
            errors.append(f"梗概复检未绑定当前材料：{key}")
    return errors


def current_reference() -> tuple[str, str, str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    version = str(manifest.get("skill_version") or "")
    names = (manifest.get("phases") or {}).get("episode-quality-review") or []
    if names != [REFERENCE_NAME]:
        raise ValueError("episode-quality-review 阶段必须且只能装载独立复检 reference")
    text = REFERENCE_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("逐集独立复检 reference 为空")
    return version, text, sha256(text)


def build_packet(cache_root: Path, episode_id: str) -> dict[str, Any]:
    _assert_no_unsealed_work(cache_root, episode_id, synopsis_phase=False)
    _assert_predecessors_sealed(cache_root, episode_id)
    synopsis_errors = verify_synopsis_one(cache_root, episode_id)
    if synopsis_errors:
        raise ValueError("；".join(synopsis_errors))
    return build_packet_unchecked(cache_root, episode_id)


def validate_review(packet: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    comprehension = review.get("comprehension")
    if not isinstance(comprehension, dict):
        errors.append("复检缺少结构化理解门")
        comprehension = {}
    for key, label in COMPREHENSION_FIELDS.items():
        item = comprehension.get(key)
        if not isinstance(item, dict):
            errors.append(f"理解门缺少：{label}")
            continue
        answer = str(item.get("answer") or "").strip()
        proof = str(item.get("proof") or "").strip()
        if len(answer) < 4 or len(proof) < 6:
            errors.append(f"理解门证据不完整：{label}")
        elif proof not in str(packet["script"]):
            errors.append(f"理解门证据不在完整剧本中：{label}")
        elif any(marker in answer or marker in proof for marker in COMPREHENSION_FAILURE_MARKERS):
            errors.append(f"理解门未通过：{label}")
    covered = [str(item) for item in review.get("covered_checks") or []]
    missing = [item for item in REQUIRED_CHECKS if item not in covered]
    if missing:
        errors.append("复检覆盖不完整：" + "、".join(missing))
    issues = review.get("issues")
    if issues != []:
        errors.append("复检仍有未解决问题")
    evidence = review.get("evidence")
    if not isinstance(evidence, list):
        errors.append("复检缺少逐项证据")
        evidence = []
    evidence_by_check: dict[str, dict[str, Any]] = {}
    for item in evidence:
        if isinstance(item, dict) and str(item.get("check") or "") in REQUIRED_CHECKS:
            evidence_by_check[str(item["check"])] = item
    for check in REQUIRED_CHECKS:
        item = evidence_by_check.get(check) or {}
        if check == PLAIN_LANGUAGE_CHECK:
            fields = ("dialogue_location", "dialogue_proof", "narration_location", "narration_proof")
            if any(len(str(item.get(field) or "").strip()) < (2 if field.endswith("location") else 6) for field in fields):
                errors.append(f"复检证据不完整：{check}/台词与描述必须分别举证")
            elif str(item["dialogue_proof"]).strip() not in str(packet["script"]) or str(item["narration_proof"]).strip() not in str(packet["script"]):
                errors.append(f"复检证据不在完整剧本中：{check}")
        elif check == SYNOPSIS_ALIGNMENT_CHECK:
            fields = ("synopsis_proof", "script_proof", "explanation")
            if any(len(str(item.get(field) or "").strip()) < 6 for field in fields):
                errors.append(f"复检证据不完整：{check}")
            elif str(item["synopsis_proof"]).strip() not in str(packet["synopsis"]):
                errors.append(f"梗概证据不在单集梗概中：{check}")
            elif str(item["script_proof"]).strip() not in str(packet["script"]):
                errors.append(f"正文证据不在完整剧本中：{check}")
        elif len(str(item.get("location") or "").strip()) < 2 or len(str(item.get("proof") or "").strip()) < 6:
            errors.append(f"复检证据不完整：{check}")
        elif str(item["proof"]).strip() not in str(packet["script"]):
            errors.append(f"复检证据不在完整剧本中：{check}")
    if review.get("script_sha256") != packet["script_sha256"]:
        errors.append("复检正文指纹与当前复检包不一致")
    if review.get("reference_sha256") != packet["reference_sha256"]:
        errors.append("复检 reference 指纹与当前复检包不一致")
    if review.get("user_intent_source_sha256") != packet["user_intent_source_sha256"]:
        errors.append("复检未绑定当前用户要求源文件")
    if review.get("user_intent_contract_sha256") != packet["user_intent_contract_sha256"]:
        errors.append("复检未绑定当前用户意图合同")
    return errors


def receipt_path(cache_root: Path, episode_id: str) -> Path:
    return cache_root / REVIEW_DIR / f"{episode_id}.json"


def _raw_verify_receipt(cache_root: Path, episode_id: str) -> list[str]:
    try:
        packet = build_packet_unchecked(cache_root, episode_id)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    path = receipt_path(cache_root, episode_id)
    if not path.is_file():
        return [f"缺少当前有效的逐集复检回执：{episode_id}"]
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [f"逐集复检回执不可读取：{episode_id}"]
    errors: list[str] = []
    for key in (
        "packet_version", "episode_id", "script_sha256", "reference_name",
        "reference_sha256", "user_intent_source_sha256",
        "user_intent_contract_sha256", "required_checks",
    ):
        if receipt.get(key) != packet.get(key):
            errors.append(f"逐集复检回执已失效：{episode_id}/{key}")
    if validate_review(packet, receipt):
        errors.append(f"逐集复检证据无效：{episode_id}")
    return list(dict.fromkeys(errors))


def _assert_predecessors_sealed(cache_root: Path, episode_id: str) -> None:
    nodes = parse(cache_root / "topology.md")
    if episode_id not in nodes:
        raise ValueError(f"冻结拓扑不存在分集：{episode_id}")
    for predecessor in predecessors(nodes)[episode_id]:
        errors = _raw_verify_receipt(cache_root, predecessor)
        if errors:
            raise ValueError(f"直接前置分集尚未放行：{predecessor}")


def _assert_no_unsealed_work(cache_root: Path, episode_id: str, *, synopsis_phase: bool) -> None:
    for path in sorted((cache_root / "episodes").glob("episode-*.md")):
        if path.stem == episode_id:
            continue
        if _raw_verify_receipt(cache_root, path.stem):
            raise ValueError(f"检测到抢跑正文，必须先完成当前逐集放行：{path.stem}")
    for path in sorted((cache_root / SYNOPSIS_DIR).glob("episode-*.json")):
        if path.stem == episode_id:
            continue
        if verify_synopsis_one(cache_root, path.stem):
            raise ValueError(f"检测到未放行的其他梗概，必须一次只处理一集：{path.stem}")


def build_packet_unchecked(cache_root: Path, episode_id: str) -> dict[str, Any]:
    path, artifact = read_episode(cache_root, episode_id)
    script = complete_script(artifact)
    _, synopsis_data = read_synopsis(cache_root, episode_id)
    artifact_synopsis = subsection(section(artifact, "分集剧本"), "单集梗概")
    artifact_conflict = subsection(section(artifact, "剧本分析"), "本集冲突")
    synopsis_errors = verify_synopsis_one(cache_root, episode_id)
    if synopsis_errors:
        raise ValueError("；".join(synopsis_errors))
    if artifact_synopsis != synopsis_data["synopsis"]:
        raise ValueError(f"完整剧本中的单集梗概与已通过理解门的梗概不一致：{episode_id}")
    if artifact_conflict != synopsis_data["conflict"]:
        raise ValueError(f"完整剧本中的本集冲突与已通过理解门的冲突不一致：{episode_id}")
    version, reference, reference_sha = current_reference()
    user_source_sha, user_contract_sha = contract_binding(cache_root)
    return {
        "packet_version": "episode-quality-gate-v3",
        "skill_version": version,
        "episode_id": episode_id,
        "script_path": str(path),
        "script_sha256": sha256(artifact),
        "reference_name": REFERENCE_NAME,
        "reference_sha256": reference_sha,
        "user_intent_source_sha256": user_source_sha,
        "user_intent_contract_sha256": user_contract_sha,
        "required_checks": REQUIRED_CHECKS,
        "reference": reference,
        "synopsis": artifact_synopsis,
        "script": script,
    }


def seal_synopsis(cache_root: Path, episode_id: str, review_path: Path) -> Path:
    packet = synopsis_packet(cache_root, episode_id)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    errors = validate_synopsis_review(packet, review)
    if errors:
        raise ValueError("；".join(errors))
    receipt = {
        "packet_version": packet["packet_version"],
        "skill_version": packet["skill_version"],
        "episode_id": episode_id,
        "synopsis_sha256": packet["synopsis_sha256"],
        "user_intent_source_sha256": packet["user_intent_source_sha256"],
        "user_intent_contract_sha256": packet["user_intent_contract_sha256"],
        "comprehension": review["comprehension"],
        "issues": [],
        "note": str(review.get("note") or ""),
    }
    output = synopsis_receipt_path(cache_root, episode_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def verify_synopsis_one(cache_root: Path, episode_id: str) -> list[str]:
    try:
        path, _ = read_synopsis(cache_root, episode_id)
        user_source_sha, user_contract_sha = contract_binding(cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    receipt_path_value = synopsis_receipt_path(cache_root, episode_id)
    if not receipt_path_value.is_file():
        return [f"缺少当前有效的梗概理解回执：{episode_id}"]
    try:
        receipt = json.loads(receipt_path_value.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [f"梗概理解回执不可读取：{episode_id}"]
    packet = {
        "synopsis_sha256": sha256(path.read_text(encoding="utf-8").strip()),
        "user_intent_source_sha256": user_source_sha,
        "user_intent_contract_sha256": user_contract_sha,
        "synopsis": json.loads(path.read_text(encoding="utf-8"))["synopsis"],
    }
    errors = validate_synopsis_review(packet, receipt)
    if receipt.get("packet_version") != SYNOPSIS_PACKET_VERSION or receipt.get("episode_id") != episode_id:
        errors.append(f"梗概理解回执合同或编号错误：{episode_id}")
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
        "script_sha256": packet["script_sha256"],
        "reference_name": packet["reference_name"],
        "reference_sha256": packet["reference_sha256"],
        "user_intent_source_sha256": packet["user_intent_source_sha256"],
        "user_intent_contract_sha256": packet["user_intent_contract_sha256"],
        "required_checks": REQUIRED_CHECKS,
        "comprehension": review["comprehension"],
        "covered_checks": review["covered_checks"],
        "evidence": review["evidence"],
        "issues": [],
        "note": str(review.get("note") or ""),
    }
    output = receipt_path(cache_root, episode_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def verify_project(cache_root: Path) -> list[str]:
    errors: list[str] = []
    episode_ids = sorted(path.stem for path in (cache_root / "episodes").glob("episode-*.md"))
    if not episode_ids:
        return ["没有可复检的分集正文"]
    for episode_id in episode_ids:
        synopsis_errors = verify_synopsis_one(cache_root, episode_id)
        if synopsis_errors:
            errors.extend(synopsis_errors)
        packet = build_packet(cache_root, episode_id)
        path = receipt_path(cache_root, episode_id)
        if not path.is_file():
            errors.append(f"缺少当前有效的逐集复检回执：{episode_id}")
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append(f"逐集复检回执不可读取：{episode_id}")
            continue
        # skill_version is provenance only. A global Skill bump must not invalidate
        # a receipt when its actual dependencies remain identical.
        for key in (
            "packet_version",
            "episode_id",
            "script_sha256",
            "reference_name",
            "reference_sha256",
            "user_intent_source_sha256",
            "user_intent_contract_sha256",
            "required_checks",
        ):
            if receipt.get(key) != packet.get(key):
                errors.append(f"逐集复检回执已失效：{episode_id}/{key}")
        if receipt.get("covered_checks") is None or any(check not in receipt.get("covered_checks", []) for check in REQUIRED_CHECKS):
            errors.append(f"逐集复检覆盖不完整：{episode_id}")
        if receipt.get("issues") != []:
            errors.append(f"逐集复检仍有问题：{episode_id}")
        if validate_review(packet, receipt):
            errors.append(f"逐集复检证据无效：{episode_id}")
    return list(dict.fromkeys(errors))


def verify_one(cache_root: Path, episode_id: str) -> list[str]:
    packet = build_packet(cache_root, episode_id)
    path = receipt_path(cache_root, episode_id)
    if not path.is_file():
        return [f"缺少当前有效的逐集复检回执：{episode_id}"]
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [f"逐集复检回执不可读取：{episode_id}"]
    errors: list[str] = []
    for key in (
        "packet_version",
        "episode_id",
        "script_sha256",
        "reference_name",
        "reference_sha256",
        "user_intent_source_sha256",
        "user_intent_contract_sha256",
        "required_checks",
    ):
        if receipt.get(key) != packet.get(key):
            errors.append(f"逐集复检回执已失效：{episode_id}/{key}")
    if validate_review(packet, receipt):
        errors.append(f"逐集复检证据无效：{episode_id}")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    packet_parser = subparsers.add_parser("packet")
    packet_parser.add_argument("cache_root", type=Path)
    packet_parser.add_argument("episode_id")
    packet_parser.add_argument("--output", type=Path)
    synopsis_packet_parser = subparsers.add_parser("synopsis-packet")
    synopsis_packet_parser.add_argument("cache_root", type=Path)
    synopsis_packet_parser.add_argument("episode_id")
    synopsis_packet_parser.add_argument("--output", type=Path)
    synopsis_seal_parser = subparsers.add_parser("synopsis-seal")
    synopsis_seal_parser.add_argument("cache_root", type=Path)
    synopsis_seal_parser.add_argument("episode_id")
    synopsis_seal_parser.add_argument("review", type=Path)
    synopsis_verify_parser = subparsers.add_parser("synopsis-verify-one")
    synopsis_verify_parser.add_argument("cache_root", type=Path)
    synopsis_verify_parser.add_argument("episode_id")
    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("cache_root", type=Path)
    seal_parser.add_argument("episode_id")
    seal_parser.add_argument("review", type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("cache_root", type=Path)
    verify_one_parser = subparsers.add_parser("verify-one")
    verify_one_parser.add_argument("cache_root", type=Path)
    verify_one_parser.add_argument("episode_id")
    args = parser.parse_args()
    try:
        if args.command in {"packet", "synopsis-packet"}:
            packet_value = (
                build_packet(args.cache_root, args.episode_id)
                if args.command == "packet"
                else synopsis_packet(args.cache_root, args.episode_id)
            )
            packet_text = json.dumps(
                packet_value,
                ensure_ascii=False,
                indent=2,
            ) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(packet_text, encoding="utf-8")
                print(f"PASS: {args.output}")
            else:
                print(packet_text, end="")
        elif args.command == "synopsis-seal":
            print(f"PASS: {seal_synopsis(args.cache_root, args.episode_id, args.review)}")
        elif args.command == "synopsis-verify-one":
            errors = verify_synopsis_one(args.cache_root, args.episode_id)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}")
                return 1
            print(f"PASS: {args.episode_id} has a current synopsis-comprehension receipt")
        elif args.command == "seal":
            print(f"PASS: {seal(args.cache_root, args.episode_id, args.review)}")
        elif args.command == "verify":
            errors = verify_project(args.cache_root)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}")
                return 1
            print("PASS: every episode has a current reference-bound quality-review receipt")
        else:
            errors = verify_one(args.cache_root, args.episode_id)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}")
                return 1
            print(f"PASS: {args.episode_id} has a current reference-bound quality-review receipt")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
