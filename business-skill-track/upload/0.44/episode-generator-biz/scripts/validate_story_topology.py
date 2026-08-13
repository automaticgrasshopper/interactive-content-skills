#!/usr/bin/env python3
"""Ensure the frozen topology is a projection of the reviewed complete story."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from story_treatment_gate import read_treatment, verify as verify_treatment
from decision_fissure_gate import read_audit
from validate_topology import parse


def validate(treatment_path: Path, topology_path: Path, expected_endings: int | None) -> list[str]:
    cache_root = treatment_path.parent
    issues = verify_treatment(cache_root)
    if treatment_path.name != "story-treatment.json":
        issues.append("完整故事文件名必须为 story-treatment.json")
    _, treatment = read_treatment(cache_root)
    _, audit = read_audit(cache_root)
    nodes = parse(topology_path)

    story_choices = treatment["choices"]
    topology_choices = {
        str(node["question"]): node
        for node in nodes.values()
        if node["choices"]
    }
    if len(topology_choices) != len([node for node in nodes.values() if node["choices"]]):
        issues.append("拓扑存在重复选择问题")
    story_questions = [str(choice["question"]).strip() for choice in story_choices]
    if set(story_questions) != set(topology_choices):
        missing = sorted(set(story_questions) - set(topology_choices))
        added = sorted(set(topology_choices) - set(story_questions))
        if missing:
            issues.append(f"完整故事中的选择未投影到拓扑：{missing}")
        if added:
            issues.append(f"拓扑新增了完整故事不存在的选择：{added}")
    for choice in story_choices:
        question = str(choice["question"]).strip()
        node = topology_choices.get(question)
        if not node:
            continue
        story_options = {str(option["option_text"]).strip() for option in choice["options"]}
        topology_options = {str(text).strip() for text, _ in node["choices"]}
        if story_options != topology_options:
            issues.append(f"选择选项与完整故事不一致：{question}")

    main_story_endings = {str(ending["title"]).strip() for ending in treatment["endings"]}
    minor_story_endings = {str(ending["title"]).strip() for ending in treatment["minor_endings"]}
    story_endings = main_story_endings | minor_story_endings
    topology_endings = {
        str(node["title"]).strip()
        for node in nodes.values()
        if bool(node["ending"])
    }
    if story_endings != topology_endings:
        missing = sorted(story_endings - topology_endings)
        added = sorted(topology_endings - story_endings)
        if missing:
            issues.append(f"完整故事中的结局未投影到拓扑：{missing}")
        if added:
            issues.append(f"拓扑新增了完整故事不存在的结局：{added}")
    if expected_endings is not None and len(main_story_endings) != expected_endings:
        issues.append(f"完整故事主要结局数错误：期望{expected_endings}，实际{len(main_story_endings)}；独立小结局不计入")
    minor_by_action = {str(item["source_action_id"]): item for item in treatment["minor_endings"]}
    topology_by_question = {str(node["question"]): node for node in nodes.values() if node["choices"]}
    node_id_by_title = {str(node["title"]): node_id for node_id, node in nodes.items()}
    for fissure in audit["fissures"]:
        question = str(fissure["decision_question"])
        choice_node = topology_by_question.get(question)
        if not choice_node:
            continue
        targets_by_text = {str(text): str(target) for text, target in choice_node["choices"]}
        for action in fissure["actions"]:
            if not (action.get("route_ended") is True and action.get("ending_scope") == "minor"):
                continue
            action_id = str(action["action_id"])
            ending = minor_by_action.get(action_id)
            if not ending:
                continue
            target = targets_by_text.get(str(action["action_text"]))
            expected_target = node_id_by_title.get(str(ending["title"]))
            if not target or target != expected_target:
                issues.append(f"提前终止动作必须直接指向自己的独立小结局：{action_id}")
                continue
            target_node = nodes[target]
            if not target_node["ending"] or "独立小结局" not in str(target_node["interaction"]):
                issues.append(f"独立小结局必须是不可继续的专属终点：{action_id}->{target}")
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("treatment", type=Path)
    parser.add_argument("topology", type=Path)
    parser.add_argument("--expected-endings", type=int)
    args = parser.parse_args()
    try:
        issues = validate(args.treatment, args.topology, args.expected_endings)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: topology choices and endings are projected from the reviewed complete story")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
