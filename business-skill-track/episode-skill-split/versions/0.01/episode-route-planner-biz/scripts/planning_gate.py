#!/usr/bin/env python3
"""Validate the private mainline-first planning closure for one route candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import deque
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "nextplay.route-planning-evidence.v1"
RECEIPT_VERSION = "nextplay.route-planning-acceptance.v2"
HASH = re.compile(r"[0-9a-f]{64}")
REVIEW_CHECKS = {
    "A": (
        "主线投影无遗漏改写",
        "采用的决定裂缝真实成立",
        "选项即时后果互异且可见",
        "未结束路线持续承接差异",
        "汇合具有共同事实基础",
    ),
    "B": (
        "四类结局兑现完整",
        "每个节点是必要戏剧单位",
        "拓扑没有被固定形状挤压",
        "期望结局能力具有上游来源",
    ),
}

REQUIRED_FILES = (
    "user-request.md",
    "user-intent-lock.json",
    "creative-brief.json",
    "complete-story.json",
    "complete-story-review.json",
    "mainline-decomposition.json",
    "mainline-emotional-movement.json",
    "decision-fissure-audit.json",
    "decision-fissure-review.json",
    "story-treatment.json",
    "story-treatment-review.json",
    "topology-draft-1.json",
    "route-candidate.json",
    "topology-review-packet.json",
    "topology-review-a.json",
    "topology-review-b.json",
    "emotional-spine.json",
    "route-material-review.json",
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_planning_files(cache_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = cache_root.resolve()
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError("规划验收缺少阶段产物：" + "、".join(missing))
    candidate = load_json(root / "route-candidate.json")
    complete_story = load_json(root / "complete-story.json")
    decomposition = load_json(root / "mainline-decomposition.json")
    movements = load_json(root / "mainline-emotional-movement.json")
    fissures = load_json(root / "decision-fissure-audit.json")
    treatment = load_json(root / "story-treatment.json")
    draft = load_json(root / "topology-draft-1.json")
    spine = load_json(root / "emotional-spine.json")
    review_a = load_json(root / "topology-review-a.json")
    review_b = load_json(root / "topology-review-b.json")
    evidence = {
        "contract_version": CONTRACT_VERSION,
        "project_id": candidate.get("project_id"),
        "route_id": candidate.get("route_id"),
        "route_version": candidate.get("route_version"),
        "route_input_hash": candidate.get("route_input_hash"),
        "route_candidate_hash": digest(candidate),
        "complete_story": complete_story,
        "mainline_segments": decomposition.get("mainline_segments"),
        "emotional_movements": movements.get("emotional_movements"),
        "decision_fissures": fissures.get("decision_fissures"),
        "story_treatment": treatment,
        "topology_draft_1": draft,
        "emotional_spine": spine.get("emotional_spine"),
        "reviews": [review_a, review_b],
    }
    return candidate, evidence


def exact_fields(value: Any, fields: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict) or set(value) != fields:
        errors.append(f"{label}字段错误")
        return False
    return True


def graph_shape(nodes: list[dict[str, Any]]) -> str:
    by_id = {str(node.get("node_id")): node for node in nodes if isinstance(node, dict)}
    if "episode-001" not in by_id:
        return ""
    order: list[str] = []
    queued = {"episode-001"}
    queue = deque(["episode-001"])
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in by_id[node_id].get("后续节点编号列表", []):
            if target in by_id and target not in queued:
                queued.add(target)
                queue.append(target)
    indexes = {node_id: index for index, node_id in enumerate(order)}
    payload = []
    for node_id in order:
        node = by_id[node_id]
        payload.append({
            "kind": "ending" if node.get("是否结局") else ("choice" if node.get("互动节点", {}).get("是否为分支节点") else "story"),
            "ending_type": node.get("ending_type"),
            "successors": [indexes[target] for target in node.get("后续节点编号列表", []) if target in indexes],
        })
    return digest(payload)


def draft_shape(draft: Any) -> str:
    if not isinstance(draft, dict) or set(draft) != {"entry_node_id", "nodes"}:
        return ""
    nodes = draft.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return ""
    by_id = {str(node.get("node_id")): node for node in nodes if isinstance(node, dict)}
    entry = draft.get("entry_node_id")
    if entry not in by_id:
        return ""
    order: list[str] = []
    queued = {entry}
    queue = deque([entry])
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        successors = by_id[node_id].get("successors")
        if not isinstance(successors, list):
            return ""
        for target in successors:
            if target not in by_id:
                return ""
            if target not in queued:
                queued.add(target)
                queue.append(target)
    if len(order) != len(by_id):
        return ""
    indexes = {node_id: index for index, node_id in enumerate(order)}
    payload = []
    for node_id in order:
        node = by_id[node_id]
        if set(node) != {"node_id", "kind", "ending_type", "successors"}:
            return ""
        payload.append({
            "kind": node["kind"],
            "ending_type": node["ending_type"],
            "successors": [indexes[target] for target in node["successors"]],
        })
    return digest(payload)


def reachable(successors: dict[str, list[str]], start: str, target: str) -> bool:
    seen: set[str] = set()
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        queue.extend(successors.get(current, []))
    return False


def validate(candidate: Any, evidence: Any) -> list[str]:
    errors: list[str] = []
    root_fields = {
        "contract_version", "project_id", "route_id", "route_version", "route_input_hash",
        "route_candidate_hash", "complete_story", "mainline_segments", "emotional_movements",
        "decision_fissures", "story_treatment", "topology_draft_1", "emotional_spine", "reviews",
    }
    if not exact_fields(evidence, root_fields, "规划证据根对象", errors):
        return errors
    if evidence["contract_version"] != CONTRACT_VERSION:
        errors.append("规划证据合同版本错误")
    if not isinstance(candidate, dict):
        return errors + ["候选路线必须是对象"]
    for field in ("project_id", "route_id", "route_version", "route_input_hash"):
        if evidence.get(field) != candidate.get(field):
            errors.append(f"规划证据未绑定当前{field}")
    if evidence.get("route_candidate_hash") != digest(candidate):
        errors.append("规划证据未绑定当前候选路线")

    nodes = candidate.get("nodes") if isinstance(candidate.get("nodes"), list) else []
    by_id = {str(node.get("node_id")): node for node in nodes if isinstance(node, dict)}
    successors = {node_id: list(node.get("后续节点编号列表", [])) for node_id, node in by_id.items()}
    story = evidence.get("complete_story")
    if not exact_fields(story, {"contract_version", "title", "complete_story"}, "完整故事", errors):
        story_text = ""
    else:
        story_text = str(story.get("complete_story") or "").strip()
        if story.get("contract_version") != "nextplay.episode-complete-story.v1" or len(story_text) < 120:
            errors.append("完整故事合同错误或内容不足")

    segments = evidence.get("mainline_segments")
    segment_by_id: dict[str, dict[str, Any]] = {}
    mainline_node_ids: list[str] = []
    if not isinstance(segments, list) or not segments:
        errors.append("缺少主线连续切分")
        segments = []
    for index, segment in enumerate(segments):
        if not exact_fields(segment, {"segment_id", "source_text", "route_node_id"}, f"主线切片/{index}", errors):
            continue
        segment_id = str(segment["segment_id"])
        node_id = str(segment["route_node_id"])
        if segment_id in segment_by_id or node_id not in by_id or node_id in mainline_node_ids:
            errors.append(f"主线切片身份或路线映射错误：{segment_id}")
            continue
        segment_by_id[segment_id] = segment
        mainline_node_ids.append(node_id)
    combined = "".join(str(segment.get("source_text") or "") for segment in segments)
    if story_text and normalized_text(combined) != normalized_text(story_text):
        errors.append("主线切片没有连续无遗漏覆盖完整故事")
    for source, target in zip(mainline_node_ids, mainline_node_ids[1:]):
        if target not in successors.get(source, []):
            errors.append(f"主线原动作未保持为直接后继：{source}->{target}")

    movements = evidence.get("emotional_movements")
    movement_by_id: dict[str, dict[str, Any]] = {}
    covered_segments: set[str] = set()
    movement_fields = {
        "movement_id", "segment_ids", "source_proof", "pressure", "desired_state",
        "reality_shift", "control_change", "unresolved_task", "candidate_fissures",
    }
    if not isinstance(movements, list) or not movements:
        errors.append("缺少拓扑前主线情绪运动")
        movements = []
    for index, movement in enumerate(movements):
        if not exact_fields(movement, movement_fields, f"情绪运动/{index}", errors):
            continue
        movement_id = str(movement["movement_id"])
        segment_ids = movement["segment_ids"]
        if movement_id in movement_by_id or not isinstance(segment_ids, list) or not segment_ids or any(item not in segment_by_id for item in segment_ids):
            errors.append(f"情绪运动引用错误：{movement_id}")
            continue
        corpus = "\n".join(str(segment_by_id[item]["source_text"]) for item in segment_ids)
        proof = str(movement["source_proof"] or "").strip()
        if len(proof) < 8 or proof not in corpus:
            errors.append(f"情绪运动缺少主线逐字证据：{movement_id}")
        for field in ("pressure", "desired_state", "reality_shift", "control_change", "unresolved_task"):
            if len(str(movement[field] or "").strip()) < 6:
                errors.append(f"情绪运动缺少{field}：{movement_id}")
        if not isinstance(movement["candidate_fissures"], list):
            errors.append(f"情绪运动候选裂缝错误：{movement_id}")
        movement_by_id[movement_id] = movement
        covered_segments.update(segment_ids)
    if set(segment_by_id) != covered_segments:
        errors.append("情绪运动未覆盖全部主线切片")

    fissures = evidence.get("decision_fissures")
    fissure_fields = {
        "fissure_id", "source_node_id", "mainline_position_proof", "emotional_movement_ids",
        "decision_question", "actions", "merge_node_id", "merge_common_fact",
    }
    action_fields = {
        "option_text", "target_node_id", "immediate_consequence", "persistent_differences",
        "core_goal_status", "consumed_at_node_ids",
    }
    branch_nodes = {
        node_id for node_id, node in by_id.items()
        if isinstance(node.get("互动节点"), dict) and node["互动节点"].get("是否为分支节点") is True
    }
    covered_branches: set[str] = set()
    if not isinstance(fissures, list):
        errors.append("决定裂缝必须是数组")
        fissures = []
    for index, fissure in enumerate(fissures):
        if not exact_fields(fissure, fissure_fields, f"决定裂缝/{index}", errors):
            continue
        source = str(fissure["source_node_id"])
        if source not in branch_nodes or source not in mainline_node_ids or source in covered_branches:
            errors.append(f"主线选择没有唯一主线裂缝来源：{source}")
            continue
        proof = str(fissure["mainline_position_proof"] or "").strip()
        segment = next((item for item in segments if item.get("route_node_id") == source), None)
        if not segment or len(proof) < 8 or proof not in str(segment["source_text"]):
            errors.append(f"决定裂缝证据不在对应主线切片：{source}")
        movement_ids = fissure["emotional_movement_ids"]
        if not isinstance(movement_ids, list) or not movement_ids or any(item not in movement_by_id for item in movement_ids):
            errors.append(f"决定裂缝未绑定有效情绪运动：{source}")
        if len(str(fissure["decision_question"] or "").strip()) < 6:
            errors.append(f"决定裂缝问题不足：{source}")
        route_options = by_id[source]["互动节点"]["选项列表"]
        expected_actions = {(str(item["选项文字"]), str(item["目标分集编号"])) for item in route_options}
        actions = fissure["actions"]
        if not isinstance(actions, list) or len(actions) < 2:
            errors.append(f"决定裂缝动作不足：{source}")
            continue
        actual_actions: set[tuple[str, str]] = set()
        consequences: set[str] = set()
        continuing_targets: list[str] = []
        for action_index, action in enumerate(actions):
            if not exact_fields(action, action_fields, f"决定裂缝/{source}/动作/{action_index}", errors):
                continue
            target = str(action["target_node_id"])
            option = str(action["option_text"])
            consequence = str(action["immediate_consequence"] or "").strip()
            differences = action["persistent_differences"]
            consumed = action["consumed_at_node_ids"]
            if len(consequence) < 10 or consequence in consequences:
                errors.append(f"选项即时后果缺失或重复：{source}->{target}")
            if not isinstance(differences, dict) or not differences or any(not str(key).strip() or not str(value).strip() for key, value in differences.items()):
                errors.append(f"选项缺少持续差异：{source}->{target}")
            if not isinstance(consumed, list) or any(item not in by_id or not reachable(successors, target, item) for item in consumed):
                errors.append(f"持续差异消费节点非法：{source}->{target}")
            elif action["core_goal_status"] == "continuing" and not consumed:
                errors.append(f"未结束路线没有消费持续差异：{source}->{target}")
            elif action["core_goal_status"] == "continuing" and isinstance(differences, dict):
                for key, value in differences.items():
                    if not any(
                        str(key) in json.dumps(by_id[node_id].get("route_material", {}), ensure_ascii=False)
                        and str(value) in json.dumps(by_id[node_id].get("route_material", {}), ensure_ascii=False)
                        for node_id in consumed
                    ):
                        errors.append(f"持续差异未被登记节点实际消费：{source}->{target}/{key}={value}")
            if action["core_goal_status"] not in {"continuing", "achieved", "failed", "abandoned", "unreachable"}:
                errors.append(f"核心目标状态非法：{source}->{target}")
            if action["core_goal_status"] == "continuing":
                continuing_targets.append(target)
            actual_actions.add((option, target))
            consequences.add(consequence)
        if actual_actions != expected_actions:
            errors.append(f"决定裂缝动作与正式选项不一致：{source}")
        mainline_index = mainline_node_ids.index(source)
        if mainline_index + 1 < len(mainline_node_ids) and mainline_node_ids[mainline_index + 1] not in {target for _, target in actual_actions}:
            errors.append(f"主线原动作没有保留为正式选项：{source}")
        merge = fissure["merge_node_id"]
        common_fact = str(fissure["merge_common_fact"] or "").strip()
        if len(continuing_targets) >= 2:
            if merge not in by_id or len(common_fact) < 10 or any(not reachable(successors, target, merge) for target in continuing_targets):
                errors.append(f"回汇缺少共同事实或可达基础：{source}")
            else:
                merge_material = json.dumps(by_id[merge].get("route_material", {}), ensure_ascii=False)
                for action in actions:
                    if not isinstance(action, dict) or action.get("core_goal_status") != "continuing":
                        continue
                    for key, value in action.get("persistent_differences", {}).items():
                        if str(key) not in merge_material or str(value) not in merge_material:
                            errors.append(f"回汇节点抹掉持续差异：{source}->{merge}/{key}={value}")
        elif merge is not None and (merge not in by_id or len(common_fact) < 10):
            errors.append(f"回汇声明非法：{source}")
        covered_branches.add(source)
    mainline_branches = branch_nodes & set(mainline_node_ids)
    if covered_branches != mainline_branches:
        errors.append(f"主线选择未全部经过主线裂缝审计：{sorted(mainline_branches - covered_branches)}")

    treatment = evidence.get("story_treatment")
    treatment_choices = treatment.get("choices") if isinstance(treatment, dict) else None
    choice_fields = {"choice_id", "dramatic_cause", "question", "options", "merge_or_ending"}
    treatment_option_fields = {"option_id", "option_text", "immediate_consequence", "lasting_difference"}
    treatment_by_question: dict[str, dict[str, Any]] = {}
    if not isinstance(treatment_choices, list) or not treatment_choices:
        errors.append("支线事实登记缺少choices")
        treatment_choices = []
    for index, choice in enumerate(treatment_choices):
        if not exact_fields(choice, choice_fields, f"支线事实选择/{index}", errors):
            continue
        choice_id = str(choice["choice_id"] or "").strip()
        question = str(choice["question"] or "").strip()
        if not choice_id.startswith("choice-") or len(question) < 4 or question in treatment_by_question:
            errors.append(f"支线事实选择身份、问题非法或重复：{choice_id}")
            continue
        if len(str(choice["dramatic_cause"] or "").strip()) < 10 or len(str(choice["merge_or_ending"] or "").strip()) < 10:
            errors.append(f"支线事实选择缺少戏剧原因或路线去向：{choice_id}")
        options = choice["options"]
        if not isinstance(options, list) or len(options) < 2:
            errors.append(f"支线事实选择至少需要两个选项：{choice_id}")
            continue
        option_ids: set[str] = set()
        option_texts: set[str] = set()
        consequences: set[str] = set()
        differences: set[str] = set()
        for option_index, option in enumerate(options):
            if not exact_fields(option, treatment_option_fields, f"支线事实选择/{choice_id}/选项/{option_index}", errors):
                continue
            option_id = str(option["option_id"] or "").strip()
            option_text = str(option["option_text"] or "").strip()
            consequence = str(option["immediate_consequence"] or "").strip()
            difference = str(option["lasting_difference"] or "").strip()
            if not option_id or option_id in option_ids or len(option_text) < 2 or option_text in option_texts:
                errors.append(f"支线事实选项身份或文字非法：{choice_id}/{option_id}")
            if len(consequence) < 8 or consequence in consequences or len(difference) < 8 or difference in differences:
                errors.append(f"支线事实选项缺少互异后果或持续差异：{choice_id}/{option_id}")
            option_ids.add(option_id)
            option_texts.add(option_text)
            consequences.add(consequence)
            differences.add(difference)
        treatment_by_question[question] = choice

    formal_by_question: dict[str, dict[str, Any]] = {}
    for source in branch_nodes:
        interaction = by_id[source]["互动节点"]
        question = str(interaction.get("选择问题") or "").strip()
        if question in formal_by_question:
            errors.append(f"正式选择问题重复：{question}")
        formal_by_question[question] = by_id[source]
    if set(treatment_by_question) != set(formal_by_question):
        errors.append(
            "支线事实选择与正式拓扑选择不一致："
            f"缺少{sorted(set(formal_by_question) - set(treatment_by_question))}，"
            f"多余{sorted(set(treatment_by_question) - set(formal_by_question))}"
        )
    for question, node in formal_by_question.items():
        treatment_choice = treatment_by_question.get(question)
        if not treatment_choice:
            continue
        formal_options = {str(item["选项文字"]).strip() for item in node["互动节点"]["选项列表"]}
        treatment_options = {str(item["option_text"]).strip() for item in treatment_choice["options"] if isinstance(item, dict)}
        if formal_options != treatment_options:
            errors.append(f"支线事实选项与正式拓扑不一致：{question}")

    first_shape = draft_shape(evidence.get("topology_draft_1"))
    final_shape = graph_shape(nodes)
    if not first_shape:
        errors.append("第一版拓扑无效")
    elif first_shape == final_shape:
        errors.append("第一版与正式拓扑图形指纹相同")

    spine = evidence.get("emotional_spine")
    if not isinstance(spine, list) or len(spine) != len(nodes):
        errors.append("节点级情绪脊没有覆盖正式拓扑")
        spine = []
    spine_ids: list[str] = []
    turns = 0
    for index, item in enumerate(spine):
        if not exact_fields(item, {"node_id", "valence", "arousal", "dominance", "turn", "turn_reason", "source_quote"}, f"情绪脊/{index}", errors):
            continue
        node_id = str(item["node_id"])
        spine_ids.append(node_id)
        for field in ("valence", "arousal", "dominance"):
            if not isinstance(item[field], (int, float)) or isinstance(item[field], bool) or not -1 <= item[field] <= 1:
                errors.append(f"情绪脊数值非法：{node_id}/{field}")
        quote = str(item["source_quote"] or "").strip()
        corpus = json.dumps(by_id.get(node_id, {}).get("route_material", {}), ensure_ascii=False)
        if len(quote) < 6 or quote not in corpus:
            errors.append(f"情绪脊缺少节点事实证据：{node_id}")
        if not isinstance(item["turn"], bool) or (item["turn"] and len(str(item["turn_reason"] or "").strip()) < 8):
            errors.append(f"情绪脊拐点说明非法：{node_id}")
        turns += item["turn"] is True
    if spine_ids != [str(node.get("node_id")) for node in nodes] or (len(nodes) > 1 and turns == 0):
        errors.append("情绪脊顺序错误或没有真实拐点")

    review_corpus = json.dumps({key: evidence[key] for key in root_fields - {"reviews"}}, ensure_ascii=False)
    reviews = evidence.get("reviews")
    if not isinstance(reviews, list) or len(reviews) != 2:
        errors.append("必须串行提供A、B两遍拓扑复检")
        reviews = []
    by_pass = {str(review.get("review_pass")): review for review in reviews if isinstance(review, dict)}
    for review_pass, required in REVIEW_CHECKS.items():
        review = by_pass.get(review_pass)
        if not exact_fields(review, {"review_pass", "verdict", "checks", "issues"}, f"拓扑复检/{review_pass}", errors):
            continue
        if review["verdict"] != "PASS" or review["issues"] != [] or not isinstance(review["checks"], list):
            errors.append(f"拓扑复检{review_pass}未通过")
            continue
        checks = {str(item.get("check")): item for item in review["checks"] if isinstance(item, dict)}
        if set(checks) != set(required):
            errors.append(f"拓扑复检{review_pass}覆盖不完整")
            continue
        for name in required:
            item = checks[name]
            if set(item) != {"check", "passed", "explanation", "evidence_quote"} or item["passed"] is not True:
                errors.append(f"拓扑复检{review_pass}检查项非法：{name}")
                continue
            quote = str(item["evidence_quote"] or "").strip()
            if len(str(item["explanation"] or "").strip()) < 8 or len(quote) < 8 or quote not in review_corpus:
                errors.append(f"拓扑复检{review_pass}缺少当前材料逐字证据：{name}")
    return list(dict.fromkeys(errors))


def build_receipt(candidate: dict[str, Any], evidence: dict[str, Any], files: dict[str, str] | None = None) -> dict[str, Any]:
    errors = validate(candidate, evidence)
    if errors:
        raise ValueError("；".join(errors))
    return {
        "contract_version": RECEIPT_VERSION,
        "status": "PASS",
        "project_id": candidate["project_id"],
        "route_id": candidate["route_id"],
        "route_version": candidate["route_version"],
        "route_input_hash": candidate["route_input_hash"],
        "route_candidate_hash": digest(candidate),
        "planning_evidence_hash": digest(evidence),
        "files": files or {},
    }


def verify_receipt(candidate: dict[str, Any], receipt: Any) -> list[str]:
    expected_fields = {
        "contract_version", "status", "project_id", "route_id", "route_version",
        "route_input_hash", "route_candidate_hash", "planning_evidence_hash", "files",
    }
    errors: list[str] = []
    if not exact_fields(receipt, expected_fields, "规划验收回执", errors):
        return errors
    if receipt["contract_version"] != RECEIPT_VERSION or receipt["status"] != "PASS":
        errors.append("规划验收回执状态错误")
    for field in ("project_id", "route_id", "route_version", "route_input_hash"):
        if receipt[field] != candidate.get(field):
            errors.append(f"规划验收回执未绑定当前{field}")
    if receipt["route_candidate_hash"] != digest(candidate):
        errors.append("规划验收回执未绑定当前候选路线")
    if HASH.fullmatch(str(receipt["planning_evidence_hash"] or "")) is None:
        errors.append("规划验收证据哈希非法")
    if not isinstance(receipt.get("files"), dict):
        errors.append("规划验收文件哈希表非法")
    return errors


def build_from_root(cache_root: Path) -> dict[str, Any]:
    candidate, evidence = load_planning_files(cache_root)
    files = {name: file_sha256(cache_root / name) for name in REQUIRED_FILES}
    return build_receipt(candidate, evidence, files)


def verify_root(cache_root: Path) -> list[str]:
    try:
        candidate, evidence = load_planning_files(cache_root)
        receipt = load_json(cache_root / "planning-acceptance.json")
        errors = verify_receipt(candidate, receipt)
        if receipt.get("planning_evidence_hash") != digest(evidence):
            errors.append("规划阶段材料在验收后发生变化")
        current_files = {name: file_sha256(cache_root / name) for name in REQUIRED_FILES}
        if receipt.get("files") != current_files:
            errors.append("规划验收绑定的阶段文件已失效")
        return list(dict.fromkeys(errors))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("cache_root", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("cache_root", type=Path)
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
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"PLANNING_REJECTED: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
