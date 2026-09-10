#!/usr/bin/env python3
"""Accept one route projected from a verified, append-only growth history."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import route_growth
from route_contract import validate as validate_route
from shape_lock import route_satisfies_exact_lock, shape_lock_issues
from user_constraints import HARD_COUNT_FIELDS, validate_intent_lock

RECEIPT_VERSION = "nextplay.route-planning-acceptance.v3"
REVIEW_CHECKS = (
    "主线投影无遗漏改写", "采用的决定裂缝真实成立", "选项即时后果互异且可见",
    "未结束路线持续承接差异", "汇合具有共同事实基础", "结局结构兑现完整",
    "每个节点是必要戏剧单位", "拓扑没有被固定形状挤压",
    "小结局自然承载危机或未偿代价", "支线逐步生长无预设收尾",
)
RETIRED_FILES = ("story-treatment.json", "topology-draft-1.json", "topology-draft-2.json",
                 "topology-comparison-packet.json", "topology-comparison-verdict.json",
                 "topology-selection.json", "route-evidence-bindings.json")
BASE_FILES = (*route_growth.UPSTREAM_FILES, "growth-state.json", "route-candidate.json")
REQUIRED_FILES = (*BASE_FILES, "topology-review.json", "emotional-spine.json")
EXACT_REQUIRED_FILES = BASE_FILES


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def exact_fields(value: Any, fields: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict) or set(value) != fields:
        errors.append(f"{label}字段错误")
        return False
    return True


def route_counts(candidate: Any) -> dict[str, int]:
    nodes = candidate.get("nodes", []) if isinstance(candidate, dict) else []
    choices = sum(isinstance(n, dict) and n.get("互动节点", {}).get("是否为分支节点") is True for n in nodes)
    return {"episode_count": len(nodes) - choices, "choice_node_count": choices,
            "ending_count": sum(n.get("是否结局") is True for n in nodes), "total_node_count": len(nodes)}


def validate_user_counts(candidate: Any, intent: Any, errors: list[str]) -> None:
    counts = intent.get("hard_counts") if isinstance(intent, dict) else None
    if not isinstance(counts, dict) or set(counts) != HARD_COUNT_FIELDS:
        errors.append("用户意图锁必须完整列出四项hard_counts")
        return
    actual = route_counts(candidate)
    for field, expected in counts.items():
        if expected is not None and actual[field] != expected:
            errors.append(f"用户硬数量未满足：{field}要求{expected}，实际{actual[field]}")


def validate_ending_policy(candidate: Any, intent: Any, errors: list[str]) -> None:
    # Ending kinds are creative defaults, never an additional quantity gate.
    # A natural small ending is evaluated semantically only when user intent permits.
    return


def validate_upstream(root: Path, errors: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    intent = load_json(root / "user-intent-lock.json")
    validate_intent_lock((root / "user-request.md").read_text(encoding="utf-8"), intent, errors)
    story = load_json(root / "complete-story.json")
    if exact_fields(story, {"contract_version", "title", "complete_story"}, "完整故事", errors):
        if story["contract_version"] != "nextplay.episode-complete-story.v1" or not all(nonempty(story[k]) for k in ("title", "complete_story")):
            errors.append("完整故事合同错误或正文为空")
    decomposition = load_json(root / "mainline-decomposition.json")
    segments = decomposition.get("mainline_segments") if isinstance(decomposition, dict) else None
    segment_ids: set[str] = set()
    source_parts: list[str] = []
    if not isinstance(segments, list) or not segments:
        errors.append("缺少主线连续切分")
        segments = []
    for item in segments:
        if not exact_fields(item, {"segment_id", "source_text"}, "主线切片", errors):
            continue
        if not nonempty(item["segment_id"]) or item["segment_id"] in segment_ids or not nonempty(item["source_text"]):
            errors.append("主线切片身份重复或内容为空")
            continue
        segment_ids.add(item["segment_id"])
        source_parts.append(item["source_text"])
    if isinstance(story, dict) and isinstance(story.get("complete_story"), str):
        normalize = lambda s: "".join(s.split())
        if normalize("".join(source_parts)) != normalize(story["complete_story"]):
            errors.append("主线切片没有连续无遗漏覆盖完整故事")
    movement_data = load_json(root / "mainline-emotional-movement.json")
    movements = movement_data.get("emotional_movements") if isinstance(movement_data, dict) else None
    movement_ids: set[str] = set()
    covered: set[str] = set()
    if not isinstance(movements, list) or not movements:
        errors.append("缺少拓扑前主线情绪运动")
        movements = []
    for item in movements:
        fields = {"movement_id", "segment_ids", "pressure", "desired_state", "reality_shift", "control_change", "unresolved_task", "candidate_fissures"}
        if not exact_fields(item, fields, "情绪运动", errors):
            continue
        mids = item["segment_ids"]
        if not nonempty(item["movement_id"]) or item["movement_id"] in movement_ids:
            errors.append("情绪运动身份非法或重复")
        else:
            movement_ids.add(item["movement_id"])
        if not isinstance(mids, list) or not mids or any(not isinstance(s, str) or s not in segment_ids for s in mids):
            errors.append("情绪运动切片引用错误")
        else:
            covered.update(mids)
        if any(not nonempty(item[k]) for k in ("pressure", "desired_state", "reality_shift", "control_change", "unresolved_task")):
            errors.append("情绪运动必要事实为空")
        if not isinstance(item["candidate_fissures"], list):
            errors.append("候选裂缝必须为数组")
    if covered != segment_ids:
        errors.append("情绪运动未覆盖全部主线切片")
    fissure_data = load_json(root / "decision-fissure-audit.json")
    fissures = fissure_data.get("decision_fissures") if isinstance(fissure_data, dict) else None
    seen_fissures: set[str] = set()
    if not isinstance(fissures, list):
        errors.append("决定裂缝必须为数组")
        fissures = []
    for item in fissures:
        if not exact_fields(item, {"fissure_id", "source_segment_id", "emotional_movement_ids", "decision_question", "actions"}, "决定裂缝", errors):
            continue
        fid = item["fissure_id"]
        if not nonempty(fid) or fid in seen_fissures:
            errors.append("决定裂缝身份非法或重复")
        else:
            seen_fissures.add(fid)
        if not isinstance(item["source_segment_id"], str) or item["source_segment_id"] not in segment_ids:
            errors.append("决定裂缝未绑定主线切片")
        mids = item["emotional_movement_ids"]
        if not isinstance(mids, list) or not mids or any(not isinstance(m, str) or m not in movement_ids for m in mids):
            errors.append("决定裂缝未绑定情绪运动")
        if not nonempty(item["decision_question"]):
            errors.append("决定裂缝问题为空")
        actions = item["actions"]
        if not isinstance(actions, list) or len(actions) < 2:
            errors.append("决定裂缝必须有互斥动作")
            continue
        seen_actions: set[str] = set()
        for action in actions:
            if not exact_fields(action, {"option_id", "option_text"}, "裂缝动作", errors):
                continue
            if not nonempty(action["option_id"]) or action["option_id"] in seen_actions or not nonempty(action["option_text"]):
                errors.append("裂缝动作身份重复或内容为空")
            else:
                seen_actions.add(action["option_id"])
    return intent, {"segment_ids": [item["segment_id"] for item in segments if isinstance(item, dict) and "segment_id" in item], "movement_ids": movement_ids}


def validate_assets(candidate: dict[str, Any], brief: Any, errors: list[str]) -> None:
    if not isinstance(brief, dict):
        errors.append("创作简报必须为对象")
        return
    manifest = brief.get("manifest.json", {})
    project_id = brief.get("project_id", manifest.get("project_id") if isinstance(manifest, dict) else None)
    if project_id != candidate.get("project_id"):
        errors.append("正式路线项目身份未绑定可见项目清单")
    for source, alternate, target in (("角色描述", "characters", "allowed_characters"), ("场景描述", "scenes", "allowed_scenes"), ("道具描述", "props", "allowed_props")):
        cards = brief.get(source, brief.get(alternate))
        names: set[str] = set()
        if not isinstance(cards, list):
            errors.append(f"创作简报缺少正式资产列表：{source}")
            continue
        for card in cards:
            if nonempty(card):
                names.add(card)
                continue
            if not isinstance(card, dict):
                errors.append(f"正式资产卡必须为对象：{source}")
                continue
            name = card.get("name", card.get("名称"))
            if not nonempty(name):
                errors.append(f"正式资产卡缺少名称：{source}")
            else:
                names.add(name)
            for alias_key in ("aliases", "别名"):
                aliases = card.get(alias_key, [])
                if isinstance(aliases, str):
                    aliases = [aliases]
                if not isinstance(aliases, list) or any(not nonempty(a) for a in aliases):
                    errors.append(f"资产别名非法：{source}")
                else:
                    names.update(aliases)
        for node in candidate["nodes"]:
            if any(name not in names for name in node["route_material"][target]):
                errors.append(f"节点使用未登记资产：{node['node_id']}/{target}")


def validate_growth_traces(root: Path, candidate: dict[str, Any], references: dict[str, Any], errors: list[str]) -> None:
    state = route_growth.load_state(root)
    mapping = route_growth.node_id_map(root)
    projected = route_growth.projection(root)
    if candidate != projected:
        errors.append("正式候选不是生长链的唯一投影")
    segments = references["segment_ids"]
    movements = references["movement_ids"]
    mapped_segments: dict[str, list[str]] = {segment: [] for segment in segments}
    for node in state["nodes"]:
        node_id = mapping.get(node["node_id"])
        if node_id is None:
            errors.append("生长节点未映射到正式路线")
            continue
        segment = node.get("mainline_segment_id")
        if segment is not None:
            if not isinstance(segment, str) or segment not in mapped_segments:
                errors.append("生长节点主线切片引用错误")
            else:
                mapped_segments[segment].append(node_id)
        mids = node.get("emotional_movement_ids")
        if not isinstance(mids, list) or not mids or any(not isinstance(m, str) or m not in movements for m in mids):
            errors.append("生长节点未绑定有效情绪运动")
    successors = {n["node_id"]: n["后续节点编号列表"] for n in candidate["nodes"]}
    def reachable(source: str, target: str) -> bool:
        seen: set[str] = set()
        queue = [source]
        while queue:
            current = queue.pop()
            if current == target:
                return True
            if current not in seen:
                seen.add(current)
                queue.extend(successors[current])
        return False
    possible: list[str] = []
    for index, segment in enumerate(segments):
        nodes = mapped_segments[segment]
        possible = nodes if index == 0 else [n for n in nodes if any(reachable(p, n) for p in possible)]
        if not possible:
            errors.append("生长路线未保留按原文顺序可达的完整主线投影")
            break


def validate_review_spine(candidate: dict[str, Any], root: Path, errors: list[str]) -> None:
    node_ids = [node["node_id"] for node in candidate["nodes"]]
    review = load_json(root / "topology-review.json")
    if exact_fields(review, {"verdict", "checks", "issues"}, "全图语义验收", errors):
        if review["verdict"] != "PASS" or review["issues"] != [] or not isinstance(review["checks"], list):
            errors.append("全图语义验收未通过")
        else:
            checks: set[str] = set()
            for item in review["checks"]:
                if not exact_fields(item, {"check", "passed", "explanation", "node_ids"}, "语义检查项", errors):
                    continue
                if not isinstance(item["check"], str) or item["check"] in checks:
                    errors.append("语义检查项身份非法或重复")
                else:
                    checks.add(item["check"])
                ids = item["node_ids"]
                if item["passed"] is not True or not nonempty(item["explanation"]) or not isinstance(ids, list) or not ids or any(n not in node_ids for n in ids):
                    errors.append("语义检查项缺少通过判断、理由或有效节点依据")
            if checks != set(REVIEW_CHECKS):
                errors.append("全图语义验收覆盖不完整")
    data = load_json(root / "emotional-spine.json")
    spine = data.get("emotional_spine") if isinstance(data, dict) else None
    if not isinstance(spine, list):
        errors.append("情绪脊必须为数组")
        return
    actual_ids: list[str] = []
    for item in spine:
        if not exact_fields(item, {"node_id", "valence", "arousal", "dominance", "turn", "turn_reason"}, "情绪脊", errors):
            continue
        actual_ids.append(item["node_id"])
        for field in ("valence", "arousal", "dominance"):
            val = item[field]
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or not -1 <= val <= 1:
                errors.append(f"情绪脊数值非法：{item['node_id']}/{field}")
        if not isinstance(item["turn"], bool) or (item["turn"] and not nonempty(item["turn_reason"])) or not isinstance(item["turn_reason"], str):
            errors.append("情绪脊拐点说明非法")
    if actual_ids != node_ids:
        errors.append("情绪脊未按顺序覆盖全部正式节点")


def _validated_material(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    if (root / "topology-state.json").exists():
        from planned_gate import validate
        return validate(root)
    # Legacy 0.18 cache recovery retains its original growth contract.
    growth_errors = route_growth.verify_root(root)
    if growth_errors:
        raise ValueError("路线生长链未通过：" + "；".join(growth_errors))
    retired = [name for name in RETIRED_FILES if (root / name).exists()]
    if retired:
        raise ValueError("本轮不接受预写支线或旧双版拓扑文件：" + "、".join(retired))
    intent_hint = load_json(root / "user-intent-lock.json")
    names = EXACT_REQUIRED_FILES if isinstance(intent_hint, dict) and intent_hint.get("shape_mode") == "exact" else REQUIRED_FILES
    initial_files = {name: file_sha256(root / name) for name in names}
    candidate = load_json(root / "route-candidate.json")
    errors = validate_route(candidate, require_accepted=False)
    if errors:
        raise ValueError("；".join(errors))
    intent, references = validate_upstream(root, errors)
    if errors:
        raise ValueError("；".join(errors))
    validate_growth_traces(root, candidate, references, errors)
    validate_user_counts(candidate, intent, errors)
    validate_ending_policy(candidate, intent, errors)
    validate_assets(candidate, load_json(root / "creative-brief.json"), errors)
    exact = intent.get("shape_mode") == "exact"
    if exact:
        lock = intent.get("locked_shape")
        lock_errors = shape_lock_issues(lock)
        errors.extend(lock_errors)
        if not lock_errors and not route_satisfies_exact_lock(candidate, lock):
            errors.append("正式候选没有精确实现用户锁定形状")
    else:
        validate_review_spine(candidate, root, errors)
    if errors:
        raise ValueError("；".join(dict.fromkeys(errors)))
    names = EXACT_REQUIRED_FILES if exact else REQUIRED_FILES
    files = {name: file_sha256(root / name) for name in names}
    if files != initial_files:
        raise ValueError("规划验收期间阶段文件发生变化")
    return candidate, files


def build_from_root(cache_root: Path) -> dict[str, Any]:
    candidate, files = _validated_material(cache_root.resolve())
    return {
        "contract_version": RECEIPT_VERSION, "status": "PASS",
        **{key: candidate[key] for key in ("project_id", "route_id", "route_version", "route_input_hash")},
        "route_candidate_hash": digest(candidate), "planning_evidence_hash": digest(files), "files": files,
    }


def verify_receipt(candidate: dict[str, Any], receipt: Any) -> list[str]:
    errors: list[str] = []
    fields = {"contract_version", "status", "project_id", "route_id", "route_version", "route_input_hash", "route_candidate_hash", "planning_evidence_hash", "files"}
    if not exact_fields(receipt, fields, "规划验收回执", errors):
        return errors
    if receipt["contract_version"] != RECEIPT_VERSION or receipt["status"] != "PASS":
        errors.append("规划验收回执状态错误")
    for key in ("project_id", "route_id", "route_version", "route_input_hash"):
        if receipt[key] != candidate.get(key):
            errors.append(f"规划验收回执未绑定当前{key}")
    if receipt["route_candidate_hash"] != digest(candidate):
        errors.append("规划验收回执未绑定当前候选路线")
    if not isinstance(receipt["files"], dict) or receipt["planning_evidence_hash"] != digest(receipt["files"]):
        errors.append("规划验收文件哈希表或证据哈希非法")
    return errors


def verify_root(cache_root: Path) -> list[str]:
    try:
        root = cache_root.resolve()
        candidate, files = _validated_material(root)
        receipt = load_json(root / "planning-acceptance.json")
        errors = verify_receipt(candidate, receipt)
        if isinstance(receipt, dict) and receipt.get("files") != files:
            errors.append("规划验收绑定的阶段文件已失效")
        return list(dict.fromkeys(errors))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "verify"):
        sub.add_parser(command).add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "create":
            receipt = build_from_root(args.cache_root)
            atomic_json(args.cache_root / "planning-acceptance.json", receipt)
            print("PLANNING_ACCEPTED")
            print(f"PLANNING_HASH={receipt['planning_evidence_hash']}")
        else:
            errors = verify_root(args.cache_root)
            if errors:
                raise ValueError("；".join(errors))
            print("PLANNING_ACCEPTANCE_PASS")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        print(f"PLANNING_REJECTED: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
