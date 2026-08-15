#!/usr/bin/env python3
"""Build the Biz JSON only after every private stage gate passes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from completion_gate import make_handoff, make_receipt, validate_episode_artifact_closure
from episode_artifact import (
    asset_values,
    atomic_write,
    parse_options,
    predecessors,
    section,
    subsection,
    validate_change_scope,
    validate_episode,
    yes_no,
)
from validate_business_output import validate as validate_business_output
from validate_character_appearances import load_asset_catalog, validate_character_appearance_project
from validate_emotional_topology import validate_emotional_topology
from validate_topology import parse
from validate_topology_revision import validate_revision
from validate_user_intent_lock import validate_user_intent_project
from validate_run_basis import validate_basis
from mainline_story_gate import verify as verify_mainline
from decision_fissure_gate import verify as verify_fissures
from story_treatment_gate import verify as verify_treatment
from stage_two_acceptance import ending_plan, verify as verify_stage_two
from validate_route_duration import validate as validate_route_duration
from episode_acceptance import verify_all as verify_episode_acceptance
from run_state import status as run_status


BUSINESS_SKILL_VERSION = "episode-generator-biz/0.48"


def resolve_ending_counts(
    cache_root: Path,
    expected_endings: int | None,
    expected_formal: int | None,
    expected_failure: int | None,
) -> tuple[int, int, int]:
    """Resolve counts from run-basis and reject contradictory CLI input immediately."""
    plan = ending_plan(cache_root)
    supplied = {
        "total": expected_endings,
        "formal": expected_formal,
        "failure": expected_failure,
    }
    if all(value is not None for value in supplied.values()):
        assert expected_endings is not None
        assert expected_formal is not None
        assert expected_failure is not None
        if expected_endings != expected_formal + expected_failure:
            raise ValueError("参数错误：expected-endings 必须等于 expected-formal + expected-failure")
    cli_names = {"total": "endings", "formal": "formal", "failure": "failure"}
    for key, value in supplied.items():
        if value is not None and value != plan[key]:
            raise ValueError(f"参数错误：expected-{cli_names[key]}={value} 与 run-basis ending_plan.{key}={plan[key]} 不一致")
    return plan["total"], plan["formal"], plan["failure"]


def ordered_asset_values(block: str) -> list[str]:
    values: list[str] = []
    for raw in re.split(r"[、，,\n]", block):
        value = re.sub(r"^\s*[-*]\s*", "", raw).strip().strip("`")
        if value and value != "无":
            values.append(value)
    return values


def episode_object(
    node_id: str,
    node: dict[str, object],
    text: str,
) -> dict[str, Any]:
    blocks = {
        name: section(text, name)
        for name in (
            "分集编号",
            "分集标题",
            "分集剧本",
            "剧本分析",
            "关联角色",
            "关联场景",
            "关联道具",
            "是否结局",
            "互动节点",
        )
    }
    script_block = blocks["分集剧本"]
    analysis_block = blocks["剧本分析"]
    interaction_block = blocks["互动节点"]
    numbers, option_texts, option_targets = parse_options(
        subsection(interaction_block, "选项列表")
    )
    options = [
        {
            "选项编号": number,
            "选项文字": option_text,
            "目标分集编号": target,
        }
        for number, option_text, target in zip(numbers, option_texts, option_targets)
    ]
    return {
        "分集编号": node_id,
        "分集标题": str(node["title"]),
        "分集剧本": {
            "单集梗概": subsection(script_block, "单集梗概"),
            "完整剧本": subsection(script_block, "完整剧本"),
        },
        "剧本分析": {
            "本集冲突": subsection(analysis_block, "本集冲突"),
            "前置节点编号列表": re.findall(
                r"episode-\d{3}",
                subsection(analysis_block, "前置节点编号列表"),
            ),
            "后续节点编号列表": re.findall(
                r"episode-\d{3}",
                subsection(analysis_block, "后续节点编号列表"),
            ),
        },
        "关联角色": ordered_asset_values(blocks["关联角色"]),
        "关联场景": ordered_asset_values(blocks["关联场景"]),
        "关联道具": ordered_asset_values(blocks["关联道具"]),
        "是否结局": yes_no(blocks["是否结局"], "是否结局"),
        "互动节点": {
            "是否为分支节点": yes_no(
                subsection(interaction_block, "是否为分支节点"),
                "是否为分支节点",
            ),
            "是否有选择问题": yes_no(
                subsection(interaction_block, "是否有选择问题"),
                "是否有选择问题",
            ),
            "选择问题": subsection(interaction_block, "选择问题"),
            "选项列表": options,
            "默认下一分集编号": subsection(interaction_block, "默认下一分集编号"),
        },
    }


def assemble_snapshot(cache_root: Path) -> dict[str, Any]:
    """Pure O(N) mapping with no semantic gate replay."""
    nodes = parse(cache_root / "topology.md")
    episodes: list[dict[str, Any]] = []
    for node_id, node in nodes.items():
        path = cache_root / "episodes" / f"{node_id}.md"
        if not path.is_file():
            raise ValueError(f"缺少正文：{node_id}")
        episodes.append(episode_object(node_id, node, path.read_text(encoding="utf-8").strip()))
    return {"分集列表": episodes}


def build_business_output(
    cache_root: Path,
    asset_catalog_path: Path,
    character_introductions_path: Path,
    spine_path: Path,
    expected_endings: int,
    expected_formal: int | None,
    expected_failure: int | None,
    baseline: Any | None,
    baseline_root: Path | None,
    allowed_changed: set[str],
    change_scope: str,
) -> tuple[dict[str, Any], list[str]]:
    topology_path = cache_root / "topology.md"
    nodes = parse(topology_path)
    catalog = load_asset_catalog(asset_catalog_path)
    issues = verify_stage_two(cache_root)
    issues.extend(verify_episode_acceptance(cache_root))
    try:
        if run_status(cache_root).get("status") != "READY_FOR_CLOSURE":
            issues.append("原子运行状态尚未完成全部分集")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues.append(f"原子运行状态不可用：{error}")
    try:
        data = assemble_snapshot(cache_root)
    except (OSError, ValueError) as error:
        issues.append(str(error))
        data = {"分集列表": []}
    issues.extend(
        validate_character_appearance_project(
            cache_root,
            nodes,
            catalog,
            character_introductions_path,
        )
    )
    issues.extend(validate_user_intent_project(cache_root))
    issues.extend(
        validate_change_scope(
            cache_root,
            baseline_root,
            list(nodes),
            allowed_changed,
            change_scope,
        )
    )
    if not issues:
        issues.extend(
            validate_business_output(
                data,
                asset_catalog_path,
                expected_endings,
                expected_formal,
                expected_failure,
                baseline,
                allowed_changed,
                change_scope,
            )
        )
    return data, list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--completion-receipt", type=Path)
    parser.add_argument("--handoff", type=Path)
    parser.add_argument("--asset-catalog", type=Path)
    parser.add_argument("--character-introductions", type=Path)
    parser.add_argument("--spine", type=Path)
    parser.add_argument("--expected-endings", type=int)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--allowed-changed", action="append", default=[])
    parser.add_argument("--change-scope", choices=("any", "dialogue"), default="any")
    args = parser.parse_args()
    try:
        cache_root = args.cache_root.resolve()
        completion_receipt = (
            args.completion_receipt or cache_root / "completion-receipt.json"
        ).resolve()
        handoff_path = (args.handoff or cache_root / "episode-handoff.json").resolve()
        if completion_receipt == args.output.resolve():
            raise ValueError("完成凭证不得覆盖业务JSON")
        if handoff_path in {args.output.resolve(), completion_receipt}:
            raise ValueError("交接清单不得覆盖业务JSON或完成凭证")
        asset_catalog_path = (
            args.asset_catalog or cache_root / "asset-catalog.json"
        ).resolve()
        character_introductions_path = (
            args.character_introductions
            or cache_root / "character-introductions.json"
        ).resolve()
        spine_path = (
            args.spine or cache_root / "emotional-spine.json"
        ).resolve()
        expected_endings, expected_formal, expected_failure = resolve_ending_counts(
            cache_root,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
        )
        baseline = (
            json.loads(args.baseline.read_text(encoding="utf-8"))
            if args.baseline
            else None
        )
        data, issues = build_business_output(
            cache_root,
            asset_catalog_path,
            character_introductions_path,
            spine_path,
            expected_endings,
            expected_formal,
            expected_failure,
            baseline,
            args.baseline_root.resolve() if args.baseline_root else None,
            set(args.allowed_changed),
            args.change_scope,
        )
        if issues:
            print("FAIL")
            for issue in issues:
                print(f"- {issue}")
            return 1
        validate_episode_artifact_closure(cache_root)
        atomic_write(
            args.output,
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        )
        json.loads(args.output.read_text(encoding="utf-8"))
        receipt = make_receipt(
            cache_root,
            args.output.resolve(),
            asset_catalog_path,
            character_introductions_path,
            spine_path,
            BUSINESS_SKILL_VERSION,
        )
        atomic_write(
            completion_receipt,
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        )
        if json.loads(completion_receipt.read_text(encoding="utf-8")) != receipt:
            raise ValueError("完成凭证写入后读回不一致")
        handoff = make_handoff(
            cache_root,
            args.output.resolve(),
            completion_receipt,
            BUSINESS_SKILL_VERSION,
        )
        atomic_write(handoff_path, json.dumps(handoff, ensure_ascii=False, indent=2) + "\n")
        if json.loads(handoff_path.read_text(encoding="utf-8")) != handoff:
            raise ValueError("交接清单写入后读回不一致")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(
        f"PASS: {len(data['分集列表'])} episodes; "
        "all private stage gates, business output, completion receipt, and handoff verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
