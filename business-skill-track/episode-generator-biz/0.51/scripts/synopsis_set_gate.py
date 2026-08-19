#!/usr/bin/env python3
"""Freeze and verify the complete synopsis set before any episode script exists."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from episode_artifact import predecessors
from story_treatment_gate import all_text, canonical, read_treatment, verify as verify_treatment
from validate_story_topology import validate as validate_story_topology
from validate_topology import parse
from validate_user_intent_lock import contract_binding


SYNOPSIS_VERSION = "nextplay.episode-synopsis.v1"
RECEIPT_VERSION = "nextplay.episode-synopsis-set-review.v2"
RECEIPT_NAME = "synopsis-set-review.json"
REQUIRED_CHECKS = [
    "完整覆盖且无重复",
    "事件顺序与因果连续",
    "分支隔离与汇合条件",
    "结局路线承接",
    "逐集戏剧单位完整",
    "各集推进量与后段完整度",
    "选择发生前决定仍未执行",
]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def frozen_mainline_synopses(cache_root: Path) -> dict[str, str]:
    """Map mainline episode ids to verbatim frozen source text."""
    decomposition_path = cache_root / "mainline-decomposition.json"
    mainline_path = cache_root / "mainline-path.json"
    if not decomposition_path.is_file() and not mainline_path.is_file():
        return {}
    if not decomposition_path.is_file() or not mainline_path.is_file():
        raise ValueError("冻结主线材料不完整")
    decomposition = json.loads(decomposition_path.read_text(encoding="utf-8"))
    path = json.loads(mainline_path.read_text(encoding="utf-8"))
    segments = {
        str(item.get("segment_id") or ""): str(item.get("source_text") or "").strip()
        for item in decomposition.get("segments") or []
        if isinstance(item, dict)
    }
    return {
        str(item.get("episode_id") or ""): segments.get(str(item.get("segment_id") or ""), "")
        for item in path.get("path") or []
        if isinstance(item, dict)
    }


def read_synopsis_set(cache_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    nodes = parse(cache_root / "topology.md")
    folder = cache_root / "episode-synopses"
    if not folder.is_dir():
        raise ValueError("缺少全体分集梗概目录")
    paths = sorted(folder.glob("episode-*.json"))
    actual_ids = [path.stem for path in paths]
    if actual_ids != sorted(nodes):
        missing = sorted(set(nodes) - set(actual_ids))
        extra = sorted(set(actual_ids) - set(nodes))
        raise ValueError(f"梗概集合与冻结拓扑不一致：缺少{missing}，多余{extra}")
    data_by_id: dict[str, dict[str, Any]] = {}
    expected_fields = {
        "contract_version", "episode_id", "title", "synopsis", "conflict",
        "predecessors", "successors",
    }
    incoming = predecessors(nodes)
    mainline = frozen_mainline_synopses(cache_root)
    conflicts: dict[str, list[str]] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        episode_id = path.stem
        if not isinstance(data, dict) or set(data) != expected_fields:
            raise ValueError(f"单集梗概字段错误：{episode_id}")
        if data.get("contract_version") != SYNOPSIS_VERSION or data.get("episode_id") != episode_id:
            raise ValueError(f"单集梗概合同或编号错误：{episode_id}")
        synopsis = str(data.get("synopsis") or "").strip()
        if episode_id in mainline:
            if synopsis != mainline[episode_id]:
                raise ValueError(f"主线梗概必须逐字继承冻结原文：{episode_id}")
            if not synopsis or len(synopsis) > 360:
                raise ValueError(f"主线冻结切片为空或超过梗概上限：{episode_id}")
        elif not 80 <= len(synopsis) <= 360:
            raise ValueError(f"支线梗概应在80至360个字符内完整表达因果变化：{episode_id}")
        conflict = str(data.get("conflict") or "").strip()
        if len(conflict) < 6:
            raise ValueError(f"单集梗概缺少本集冲突：{episode_id}")
        conflicts.setdefault(conflict, []).append(episode_id)
        if str(data.get("title") or "").strip() != str(nodes[episode_id]["title"]):
            raise ValueError(f"单集梗概标题与冻结拓扑不一致：{episode_id}")
        if data.get("predecessors") != incoming[episode_id]:
            raise ValueError(f"单集梗概前置节点与冻结拓扑不一致：{episode_id}")
        if data.get("successors") != list(nodes[episode_id]["successors"]):
            raise ValueError(f"单集梗概后续节点与冻结拓扑不一致：{episode_id}")
        data_by_id[episode_id] = data
    repeated = {text: ids for text, ids in conflicts.items() if len(ids) > 1}
    if repeated:
        raise ValueError(f"本集冲突不得跨集复用同一句：{repeated}")
    return nodes, data_by_id


def set_hash(data_by_id: dict[str, dict[str, Any]]) -> str:
    return sha256_text(canonical([data_by_id[key] for key in sorted(data_by_id)]))


def packet(cache_root: Path, *, allow_scripts: bool = False) -> dict[str, Any]:
    treatment_errors = verify_treatment(cache_root)
    if treatment_errors:
        raise ValueError("；".join(treatment_errors))
    topology_errors = validate_story_topology(
        cache_root / "story-treatment.json", cache_root / "topology.md", None
    )
    if topology_errors:
        raise ValueError("；".join(topology_errors))
    if not allow_scripts and (cache_root / "episodes").is_dir() and any((cache_root / "episodes").glob("episode-*.md")):
        raise ValueError("梗概集合冻结前不得存在任何完整剧本")
    _, treatment = read_treatment(cache_root)
    nodes, synopses = read_synopsis_set(cache_root)
    source_sha, contract_sha = contract_binding(cache_root)
    topology_text = (cache_root / "topology.md").read_text(encoding="utf-8")
    return {
        "packet_version": RECEIPT_VERSION,
        "synopsis_set_sha256": set_hash(synopses),
        "treatment_sha256": sha256_text(canonical(treatment)),
        "topology_sha256": sha256_text(topology_text),
        "user_intent_source_sha256": source_sha,
        "user_intent_contract_sha256": contract_sha,
        "required_checks": REQUIRED_CHECKS,
        "choice_episode_ids": sorted(
            episode_id for episode_id, node in nodes.items() if node["choices"]
        ),
        "treatment": treatment,
        "topology": topology_text,
        "synopses": [synopses[key] for key in sorted(synopses)],
    }


def validate_review(packet_value: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "synopsis_set_sha256", "treatment_sha256", "topology_sha256",
        "user_intent_source_sha256", "user_intent_contract_sha256",
    ):
        if review.get(key) != packet_value.get(key):
            errors.append(f"梗概集合复检未绑定当前材料：{key}")
    covered = review.get("covered_checks")
    if not isinstance(covered, list) or any(check not in covered for check in REQUIRED_CHECKS):
        errors.append("梗概集合复检覆盖不完整")
    if review.get("issues") != []:
        errors.append("梗概集合复检仍有未解决问题")

    synopses = {
        str(item["episode_id"]): item
        for item in packet_value["synopses"]
        if isinstance(item, dict) and item.get("episode_id")
    }
    checks = review.get("episode_checks")
    if not isinstance(checks, list):
        checks = []
        errors.append("梗概集合复检缺少逐集检查")
    by_id: dict[str, dict[str, Any]] = {}
    for item in checks:
        if not isinstance(item, dict):
            continue
        episode_id = str(item.get("episode_id") or "")
        if episode_id in by_id:
            errors.append(f"梗概集合复检重复分集：{episode_id}")
        by_id[episode_id] = item
    if set(by_id) != set(synopses):
        errors.append("梗概集合复检未逐集覆盖冻结拓扑")
    treatment_corpus = all_text(packet_value["treatment"])
    proof_fields = (
        "situation_goal_proof",
        "action_resistance_adjustment_proof",
        "result_next_entry_proof",
        "conflict_proof",
    )
    for episode_id, synopsis_data in synopses.items():
        item = by_id.get(episode_id) or {}
        synopsis = str(synopsis_data["synopsis"])
        proofs = [str(item.get(field) or "").strip() for field in proof_fields]
        if any(len(proof) < 10 or proof not in synopsis for proof in proofs):
            errors.append(f"逐集戏剧单位证据不完整或不在梗概中：{episode_id}")
        elif len(set(proofs)) != len(proofs):
            errors.append(f"逐集戏剧单位不得重复使用同一证据：{episode_id}")
        source_proof = str(item.get("treatment_source_proof") or "").strip()
        if len(source_proof) < 10 or source_proof not in treatment_corpus:
            errors.append(f"梗概缺少完整故事来源证据：{episode_id}")

    choice_ids = set(packet_value.get("choice_episode_ids") or [])
    choice_nodes = {
        episode_id: synopsis_data
        for episode_id, synopsis_data in synopses.items()
        if episode_id in choice_ids
    }
    choice_checks = review.get("choice_checks")
    if not isinstance(choice_checks, list):
        choice_checks = []
        errors.append("梗概集合复检缺少逐选择未执行检查")
    choice_by_id = {
        str(item.get("episode_id") or ""): item
        for item in choice_checks
        if isinstance(item, dict)
    }
    if set(choice_by_id) != set(choice_nodes):
        errors.append("梗概集合复检未逐一覆盖全部选择节点")
    for episode_id, synopsis_data in choice_nodes.items():
        item = choice_by_id.get(episode_id) or {}
        synopsis = str(synopsis_data["synopsis"])
        proof = str(item.get("pending_decision_proof") or "").strip()
        if item.get("decision_still_pending") is not True:
            errors.append(f"选择节点梗概已提前替玩家作出决定：{episode_id}")
        if item.get("executed_options") != []:
            errors.append(f"选择节点梗概已执行一个或多个选项：{episode_id}")
        if len(proof) < 10 or proof not in synopsis:
            errors.append(f"选择尚未执行的逐字证据无效：{episode_id}")

    corpus = treatment_corpus + "\n" + "\n".join(str(item["synopsis"]) for item in packet_value["synopses"])
    evidence = review.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
        errors.append("梗概集合复检缺少集合证据")
    by_check = {str(item.get("check")): item for item in evidence if isinstance(item, dict)}
    for check in REQUIRED_CHECKS:
        item = by_check.get(check) or {}
        proof = str(item.get("proof") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        if len(proof) < 10 or len(explanation) < 8:
            errors.append(f"梗概集合复检证据不完整：{check}")
        elif proof not in corpus:
            errors.append(f"梗概集合复检证据不在当前材料中：{check}")
    return list(dict.fromkeys(errors))


def seal(cache_root: Path, review_path: Path) -> Path:
    packet_value = packet(cache_root)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    errors = validate_review(packet_value, review)
    if errors:
        raise ValueError("；".join(errors))
    receipt = {
        "packet_version": packet_value["packet_version"],
        "synopsis_set_sha256": packet_value["synopsis_set_sha256"],
        "treatment_sha256": packet_value["treatment_sha256"],
        "topology_sha256": packet_value["topology_sha256"],
        "user_intent_source_sha256": packet_value["user_intent_source_sha256"],
        "user_intent_contract_sha256": packet_value["user_intent_contract_sha256"],
        "covered_checks": review["covered_checks"],
        "episode_checks": review["episode_checks"],
        "choice_checks": review["choice_checks"],
        "evidence": review["evidence"],
        "issues": [],
    }
    output = cache_root / RECEIPT_NAME
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def verify(cache_root: Path) -> list[str]:
    try:
        packet_value = packet(cache_root, allow_scripts=True)
        path = cache_root / RECEIPT_NAME
        if not path.is_file():
            return ["缺少梗概集合当前有效回执"]
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
            print("PASS: all episode synopses have one current set-level review receipt")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
