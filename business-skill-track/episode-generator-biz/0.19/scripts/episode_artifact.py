#!/usr/bin/env python3
"""Shared parsing and validation helpers for private episode artifacts."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

FIELDS = ["分集编号", "分集标题", "分集剧本", "剧本分析", "关联角色", "关联场景", "关联道具", "是否结局", "互动节点"]
SCRIPT_SUBFIELDS = ["单集梗概", "完整剧本"]
ANALYSIS_SUBFIELDS = ["本集冲突", "前置节点编号列表", "后续节点编号列表"]
INTERACTION_SUBFIELDS = ["是否为分支节点", "是否有选择问题", "选择问题", "选项列表", "默认下一分集编号"]
EPISODE_ID = re.compile(r"episode-\d{3}")
SCENE_HEADING = re.compile(r"^【[^】·]+·[^】·]+·(?:内|外)】$")
ANNOUNCED_CHOICE = re.compile(r"(?:现在请选择|请(?:玩家)?做出选择|玩家请选择|你(?:会|将)如何选择|请选择以下)")


def section(text: str, name: str) -> str:
    match = re.search(rf"^# {re.escape(name)}\s*\n+(.*?)(?=^# |\Z)", text, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"缺少一级字段：{name}")
    return match.group(1).strip()


def subsection(block: str, name: str) -> str:
    match = re.search(rf"^## {re.escape(name)}\s*\n+(.*?)(?=^## |\Z)", block, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"缺少二级字段：{name}")
    return match.group(1).strip()


def subfields(block: str) -> list[str]:
    return re.findall(r"^## (.+?)\s*$", block, re.MULTILINE)


def asset_values(block: str) -> set[str]:
    values: set[str] = set()
    for raw in re.split(r"[、，,\n]", block):
        value = re.sub(r"^\s*[-*]\s*", "", raw).strip().strip("`")
        if value and value != "无":
            values.add(value)
    return values


def yes_no(value: str, field_name: str) -> bool:
    normalized = value.strip()
    if normalized == "是":
        return True
    if normalized == "否":
        return False
    raise ValueError(f"{field_name} 必须是 是 或 否")


def predecessors(nodes: dict[str, dict[str, object]]) -> dict[str, list[str]]:
    result = {node_id: [] for node_id in nodes}
    for source, node in nodes.items():
        for target in node["successors"]:
            if target in result:
                result[target].append(source)
    return result


def parse_options(block: str) -> tuple[list[str], list[str], list[str]]:
    numbers = re.findall(r"^-\s*选项编号：\s*(.+?)\s*$", block, re.MULTILINE)
    texts = re.findall(r"^\s+-\s*选项文字：\s*(.+?)\s*$", block, re.MULTILINE)
    targets = re.findall(r"^\s+-\s*目标分集编号：\s*(episode-\d{3})\s*$", block, re.MULTILINE)
    return numbers, texts, targets


def validate_opening_choice(script: str) -> list[str]:
    issues: list[str] = []
    lines = [
        line.strip()
        for line in script.splitlines()
        if line.strip() and SCENE_HEADING.fullmatch(line.strip()) is None
    ]
    compact = re.sub(r"\s+", "", "\n".join(lines))
    if len(compact) < 60:
        issues.append("episode-001/首集选择前实质剧情不足60字符")
    if len([line for line in lines if len(re.sub(r'\s+', '', line)) >= 4]) < 2:
        issues.append("episode-001/首集选择前实质剧情不足两行")
    if ANNOUNCED_CHOICE.search(script):
        issues.append("episode-001/正文用制作话术直接宣布选择")
    return issues


def validate_episode(
    node_id: str,
    node: dict[str, object],
    text: str,
    catalog: dict[str, Any],
    expected_predecessors: list[str],
) -> tuple[list[str], str]:
    issues: list[str] = []
    headings = re.findall(r"^# (.+?)\s*$", text, re.MULTILINE)
    if headings != FIELDS:
        return [f"九字段错误：{node_id}={headings}"], ""
    try:
        blocks = {name: section(text, name) for name in FIELDS}
    except ValueError as error:
        return [f"{node_id}/{error}"], ""
    if blocks["分集编号"] != node_id:
        issues.append(f"编号错误：{node_id}")
    if blocks["分集标题"] != str(node["title"]):
        issues.append(f"标题错误：{node_id}")
    if subfields(blocks["分集剧本"]) != SCRIPT_SUBFIELDS:
        issues.append(f"分集剧本子字段错误：{node_id}")
    if subfields(blocks["剧本分析"]) != ANALYSIS_SUBFIELDS:
        issues.append(f"剧本分析子字段错误：{node_id}")
    if subfields(blocks["互动节点"]) != INTERACTION_SUBFIELDS:
        issues.append(f"互动节点子字段错误：{node_id}")
    try:
        synopsis = subsection(blocks["分集剧本"], "单集梗概")
        full_script = subsection(blocks["分集剧本"], "完整剧本")
        analysis_prev = EPISODE_ID.findall(subsection(blocks["剧本分析"], "前置节点编号列表"))
        analysis_next = EPISODE_ID.findall(subsection(blocks["剧本分析"], "后续节点编号列表"))
        is_branch = yes_no(subsection(blocks["互动节点"], "是否为分支节点"), "是否为分支节点")
        has_question = yes_no(subsection(blocks["互动节点"], "是否有选择问题"), "是否有选择问题")
        question = subsection(blocks["互动节点"], "选择问题")
        option_block = subsection(blocks["互动节点"], "选项列表")
        default_next = subsection(blocks["互动节点"], "默认下一分集编号")
    except ValueError as error:
        return issues + [f"{node_id}/{error}"], ""
    if not synopsis or not full_script:
        issues.append(f"梗概或完整剧本为空：{node_id}")
    if re.search(r"^\s*△", full_script, re.MULTILINE) or re.search(r"^\s*出场：", full_script, re.MULTILINE):
        issues.append(f"含禁用正文格式：{node_id}")
    scene_headings = [line.strip() for line in full_script.splitlines() if line.strip().startswith("【")]
    if not scene_headings:
        issues.append(f"缺少场次标题：{node_id}")
    elif any(not SCENE_HEADING.fullmatch(line) for line in scene_headings):
        issues.append(f"场次标题格式错误：{node_id}")
    if re.search(r"^[^\n：]{1,20}：\s*[“\"]", full_script, re.MULTILINE):
        issues.append(f"对白必须使用人物：台词，不使用台词引号：{node_id}")

    unknown_scenes = asset_values(blocks["关联场景"]) - catalog["scenes"]
    unknown_props = asset_values(blocks["关联道具"]) - catalog["props"]
    if unknown_scenes:
        issues.append(f"出现非正式场景资产：{node_id}={sorted(unknown_scenes)}")
    if unknown_props:
        issues.append(f"出现非正式道具资产：{node_id}={sorted(unknown_props)}")

    if analysis_prev != expected_predecessors:
        issues.append(f"前置节点不一致：{node_id}={analysis_prev} expected={expected_predecessors}")
    expected_next = list(node["successors"])
    if analysis_next != expected_next:
        issues.append(f"后续节点不一致：{node_id}={analysis_next} expected={expected_next}")
    expected_ending = bool(node["ending"])
    try:
        if yes_no(blocks["是否结局"], "是否结局") != expected_ending:
            issues.append(f"结局标记错误：{node_id}")
    except ValueError as error:
        issues.append(f"{node_id}/{error}")

    expected_choices = list(node["choices"])
    expected_branch = bool(expected_choices)
    if node_id == "episode-001" and expected_branch:
        issues.extend(validate_opening_choice(full_script))
    if is_branch != expected_branch or has_question != expected_branch:
        issues.append(f"选择存在标记与拓扑不一致：{node_id}")
    if expected_branch and (not question or question == "无"):
        issues.append(f"选择问题为空：{node_id}")
    expected_question = str(node.get("question") or "").strip()
    if expected_branch and expected_question and question != expected_question:
        issues.append(f"选择问题与拓扑不一致：{node_id}={question} expected={expected_question}")
    if not expected_branch and question not in {"", "无"}:
        issues.append(f"非分支节点含选择问题：{node_id}")
    numbers, option_texts, option_targets = parse_options(option_block)
    if expected_branch:
        if len(numbers) != len(set(numbers)) or len(numbers) != len(expected_choices):
            issues.append(f"选项编号错误：{node_id}")
        if option_texts != [text for text, _ in expected_choices]:
            issues.append(f"选项文字与拓扑不一致：{node_id}")
        if option_targets != [target for _, target in expected_choices]:
            issues.append(f"选项目标与拓扑不一致：{node_id}")
    else:
        if numbers or option_texts or option_targets or option_block not in {"", "无"}:
            issues.append(f"非分支节点含选项：{node_id}")
    if expected_branch:
        if default_next not in expected_next:
            issues.append(f"默认下一分集不在分支目标中：{node_id}={default_next}")
    else:
        expected_default = "无" if expected_ending or len(expected_next) != 1 else expected_next[0]
        if default_next != expected_default:
            issues.append(f"默认下一分集错误：{node_id}={default_next} expected={expected_default}")
    return issues, synopsis


def normalized_dialogue_shape(text: str) -> str:
    try:
        full_script = subsection(section(text, "分集剧本"), "完整剧本")
    except ValueError:
        return text
    normalized = re.sub(r"^([^\n：]{1,20}：).*$", r"\1<DIALOGUE>", full_script, flags=re.MULTILINE)
    return text.replace(full_script, normalized)


def validate_change_scope(
    cache_root: Path,
    baseline_root: Path | None,
    node_ids: list[str],
    allowed_changed: set[str],
    change_scope: str,
) -> list[str]:
    if baseline_root is None:
        return ["局部修改校验要求 --baseline-root"] if allowed_changed or change_scope != "any" else []
    issues: list[str] = []
    current_topology = (cache_root / "topology.md").read_bytes()
    baseline_topology_path = baseline_root / "topology.md"
    if not baseline_topology_path.is_file() or baseline_topology_path.read_bytes() != current_topology:
        issues.append("局部修改期间冻结拓扑发生变化")
    if not allowed_changed:
        issues.append("使用 baseline 时必须声明 --allowed-changed")
    if not allowed_changed <= set(node_ids):
        issues.append(f"allowed-changed 含未知节点：{sorted(allowed_changed - set(node_ids))}")
    for node_id in node_ids:
        current = cache_root / "episodes" / f"{node_id}.md"
        baseline = baseline_root / "episodes" / f"{node_id}.md"
        if not baseline.is_file():
            issues.append(f"基线缺少正文：{node_id}")
            continue
        current_text = current.read_text(encoding="utf-8")
        baseline_text = baseline.read_text(encoding="utf-8")
        if node_id not in allowed_changed and current_text != baseline_text:
            issues.append(f"未授权分集发生变化：{node_id}")
        if node_id in allowed_changed and change_scope == "dialogue" and normalized_dialogue_shape(current_text) != normalized_dialogue_shape(baseline_text):
            issues.append(f"台词修改越过对白范围：{node_id}")
    return issues


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
