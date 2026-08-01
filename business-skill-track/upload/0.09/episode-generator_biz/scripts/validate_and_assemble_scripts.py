#!/usr/bin/env python3
"""Validate generic episode artifacts and deterministically build all three public files."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from episode_quality_gate import verify_project
from validate_character_appearances import load_asset_catalog, validate_character_appearance_project
from validate_emotional_topology import validate_emotional_topology
from validate_topology import parse
from validate_user_intent_lock import validate_user_intent_project


FIELDS = ["分集编号", "分集标题", "分集数", "分集剧本", "剧本分析", "关联角色", "关联场景", "关联道具", "是否结局", "选择节点", "互动节点"]
SCRIPT_SUBFIELDS = ["完整剧本", "单集梗概"]
ANALYSIS_SUBFIELDS = ["本集冲突", "前置节点编号列表", "后续节点编号列表"]
CHOICE_SUBFIELDS = ["是否为选择节点", "是否有选择问题", "选择节点编号", "选择问题", "选项列表"]
INTERACTION_SUBFIELDS = ["是否为互动节点", "互动节点编号", "后边是否接选择节点", "后续选择节点编号"]
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
    targets = re.findall(r"^\s+-\s*目标互动节点编号：\s*(episode-\d{3})\s*$", block, re.MULTILINE)
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
    expected_episode_count: int,
    expected_choice_count: int,
) -> tuple[list[str], str]:
    issues: list[str] = []
    headings = re.findall(r"^# (.+?)\s*$", text, re.MULTILINE)
    if headings != FIELDS:
        return [f"十一字段错误：{node_id}={headings}"], ""
    try:
        blocks = {name: section(text, name) for name in FIELDS}
    except ValueError as error:
        return [f"{node_id}/{error}"], ""
    if blocks["分集编号"] != node_id:
        issues.append(f"编号错误：{node_id}")
    if blocks["分集标题"] != str(node["title"]):
        issues.append(f"标题错误：{node_id}")
    if re.fullmatch(r"[1-9]\d*", blocks["分集数"]) is None:
        issues.append(f"分集数必须为正整数：{node_id}")
    elif int(blocks["分集数"]) != expected_episode_count:
        issues.append(
            f"分集数错误：{node_id}期望{expected_episode_count}，实际{blocks['分集数']}"
        )
    if subfields(blocks["分集剧本"]) != SCRIPT_SUBFIELDS:
        issues.append(f"分集剧本子字段错误：{node_id}")
    if subfields(blocks["剧本分析"]) != ANALYSIS_SUBFIELDS:
        issues.append(f"剧本分析子字段错误：{node_id}")
    if subfields(blocks["选择节点"]) != CHOICE_SUBFIELDS:
        issues.append(f"选择节点子字段错误：{node_id}")
    if subfields(blocks["互动节点"]) != INTERACTION_SUBFIELDS:
        issues.append(f"互动节点子字段错误：{node_id}")
    try:
        synopsis = subsection(blocks["分集剧本"], "单集梗概")
        full_script = subsection(blocks["分集剧本"], "完整剧本")
        analysis_prev = EPISODE_ID.findall(subsection(blocks["剧本分析"], "前置节点编号列表"))
        analysis_next = EPISODE_ID.findall(subsection(blocks["剧本分析"], "后续节点编号列表"))
        is_choice = yes_no(subsection(blocks["选择节点"], "是否为选择节点"), "是否为选择节点")
        has_question = yes_no(subsection(blocks["选择节点"], "是否有选择问题"), "是否有选择问题")
        choice_id = subsection(blocks["选择节点"], "选择节点编号")
        question = subsection(blocks["选择节点"], "选择问题")
        option_block = subsection(blocks["选择节点"], "选项列表")
        is_interaction = yes_no(subsection(blocks["互动节点"], "是否为互动节点"), "是否为互动节点")
        interaction_id = subsection(blocks["互动节点"], "互动节点编号")
        has_next_choice = yes_no(subsection(blocks["互动节点"], "后边是否接选择节点"), "后边是否接选择节点")
        next_choice_id = subsection(blocks["互动节点"], "后续选择节点编号")
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
    if not is_interaction or interaction_id != node_id:
        issues.append(f"互动节点身份错误：{node_id}")
    if node_id == "episode-001" and expected_branch:
        issues.extend(validate_opening_choice(full_script))
    if is_choice != expected_branch or has_question != expected_branch or has_next_choice != expected_branch:
        issues.append(f"选择节点布尔值与拓扑不一致：{node_id}")
    if expected_branch:
        if re.fullmatch(r"choice-\d{3}", choice_id) is None or next_choice_id != choice_id:
            issues.append(f"选择节点编号或互动连线错误：{node_id}")
    elif choice_id != "无" or next_choice_id != "无":
        issues.append(f"无选择互动节点仍声明选择节点：{node_id}")
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


def build_structure(nodes: dict[str, dict[str, object]], synopses: dict[str, str]) -> str:
    parts = ["# 分集结构"]
    for node_id, node in nodes.items():
        successors = "、".join(node["successors"]) or "无"
        episode_type = node["interaction"] if node["ending"] else "互动节点"
        parts.append(
            f"## {node_id} ｜ {node['title']}\n\n"
            f"- 类型：{episode_type}\n"
            f"- 是否结局：{'是' if node['ending'] else '否'}\n"
            f"- 单集梗概：{synopses[node_id]}\n"
            f"- 后续节点：{successors}"
        )
    return "\n\n".join(parts) + "\n"


def build_flowchart(nodes: dict[str, dict[str, object]]) -> str:
    width = 1180
    height = max(160, 120 * len(nodes) + 40)
    index = {node_id: i for i, node_id in enumerate(nodes)}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#667085"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    choice_ids = {
        node_id: f"choice-{choice_index:03d}"
        for choice_index, node_id in enumerate(
            (node_id for node_id, node in nodes.items() if node["choices"]),
            start=1,
        )
    }
    for source, node in nodes.items():
        y1 = 70 + index[source] * 120
        if source in choice_ids:
            choice_id = choice_ids[source]
            parts.append(f'<path data-edge="{source}->{choice_id}" d="M360,{y1} L500,{y1}" fill="none" stroke="#667085" stroke-width="2" marker-end="url(#arrow)"/>')
            for edge_index, target in enumerate(node["successors"]):
                if target not in index:
                    continue
                y2 = 70 + index[target] * 120
                control_x = 820 + edge_index * 35
                parts.append(f'<path data-edge="{choice_id}->{target}" d="M780,{y1} C{control_x},{y1} {control_x},{y2} 360,{y2}" fill="none" stroke="#667085" stroke-width="2" marker-end="url(#arrow)"/>')
        else:
            for edge_index, target in enumerate(node["successors"]):
                if target not in index:
                    continue
                y2 = 70 + index[target] * 120
                control_x = 430 + edge_index * 45
                parts.append(f'<path data-edge="{source}->{target}" d="M360,{y1} C{control_x},{y1} {control_x},{y2} 360,{y2}" fill="none" stroke="#667085" stroke-width="2" marker-end="url(#arrow)"/>')
    for node_id, node in nodes.items():
        y = 40 + index[node_id] * 120
        fill = "#fee4e2" if node["ending"] else "#e0f2fe"
        parts.append(f'<g data-node-id="{node_id}" data-node-type="互动节点"><rect x="40" y="{y}" width="320" height="60" rx="10" fill="{fill}" stroke="#344054"/>')
        parts.append(f'<text x="55" y="{y + 25}" font-family="sans-serif" font-size="15" fill="#101828">{html.escape(node_id)}</text>')
        parts.append(f'<text x="55" y="{y + 47}" font-family="sans-serif" font-size="14" fill="#344054">{html.escape(str(node["title"]))}</text></g>')
        if node_id in choice_ids:
            choice_id = choice_ids[node_id]
            question = html.escape(str(node.get("question") or "请选择"))
            parts.append(f'<g data-choice-id="{choice_id}" data-source-episode="{node_id}"><rect x="500" y="{y}" width="280" height="60" rx="10" fill="#ecfdf3" stroke="#027a48"/>')
            parts.append(f'<text x="515" y="{y + 25}" font-family="sans-serif" font-size="15" fill="#101828">{choice_id} ｜ 选择节点</text>')
            parts.append(f'<text x="515" y="{y + 47}" font-family="sans-serif" font-size="13" fill="#344054">{question}</text></g>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


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


def fsync_directory(path: Path) -> None:
    """Persist directory-entry changes used by the public-file transaction."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def rollback_group_transaction(journal_path: Path) -> None:
    """Restore the complete previous public-file group from an interrupted commit."""
    transaction = json.loads(journal_path.read_text(encoding="utf-8"))
    parent = journal_path.parent
    for item in transaction["files"]:
        target = Path(item["target"])
        backup = Path(item["backup"])
        staged = Path(item["staged"])
        if item["existed"]:
            if not backup.is_file():
                raise OSError(f"事务回滚缺少备份：{backup}")
            os.replace(backup, target)
        elif target.exists():
            target.unlink()
        if staged.exists():
            staged.unlink()
    journal_path.unlink()
    fsync_directory(parent)


def grouped_atomic_write(contents: list[tuple[Path, str]]) -> None:
    """Commit three public files as one recoverable transaction.

    POSIX has no multi-file rename primitive. This routine stages every file, keeps
    a complete hard-link/copy snapshot, writes a recovery journal, and rolls the
    whole group back if any replacement fails. A journal left by process or host
    interruption is rolled back before the next commit, so a failed run is never
    accepted as a valid mixed-version release.
    """
    targets = [path.resolve() for path, _ in contents]
    if len(targets) != len(set(targets)):
        raise ValueError("三个公开文件的输出路径必须互不相同")
    parents = {path.parent for path in targets}
    if len(parents) != 1:
        raise ValueError("三个公开文件必须位于同一目录，才能整组事务提交")
    parent = parents.pop()
    parent.mkdir(parents=True, exist_ok=True)
    journal_path = parent / ".nextplay-episode-public-files.transaction.json"
    if journal_path.exists():
        rollback_group_transaction(journal_path)

    records: list[dict[str, object]] = []
    journal_written = False
    try:
        for target, (_, content) in zip(targets, contents):
            staged_handle, staged_name = tempfile.mkstemp(prefix=f".{target.name}.stage.", dir=parent)
            with os.fdopen(staged_handle, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            backup_handle, backup_name = tempfile.mkstemp(prefix=f".{target.name}.backup.", dir=parent)
            os.close(backup_handle)
            os.unlink(backup_name)
            existed = target.is_file()
            if existed:
                try:
                    os.link(target, backup_name)
                except OSError:
                    shutil.copy2(target, backup_name)
            records.append(
                {
                    "target": str(target),
                    "staged": staged_name,
                    "backup": backup_name,
                    "existed": existed,
                }
            )

        atomic_write(
            journal_path,
            json.dumps({"contract_version": "nextplay.episode-public-transaction.v1", "files": records}, ensure_ascii=False, indent=2) + "\n",
        )
        journal_written = True
        fsync_directory(parent)
        for record in records:
            os.replace(str(record["staged"]), str(record["target"]))
            fsync_directory(parent)

        # Removing the journal is the commit point. Backups are deleted only after
        # it, so an interruption before this line remains fully recoverable.
        journal_path.unlink()
        journal_written = False
        fsync_directory(parent)
        for record in records:
            backup = Path(str(record["backup"]))
            if backup.exists():
                backup.unlink()
        fsync_directory(parent)
    except BaseException:
        if journal_written and journal_path.exists():
            rollback_group_transaction(journal_path)
        else:
            for record in records:
                for key in ("staged", "backup"):
                    temporary = Path(str(record[key]))
                    if temporary.exists():
                        temporary.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("output", type=Path, help="episode-script.md output")
    parser.add_argument("--asset-catalog", type=Path)
    parser.add_argument("--character-introductions", type=Path)
    parser.add_argument("--spine", type=Path)
    parser.add_argument("--expected-endings", type=int, required=True)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    parser.add_argument("--structure-output", type=Path)
    parser.add_argument("--flowchart-output", type=Path)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--allowed-changed", action="append", default=[])
    parser.add_argument("--change-scope", choices=("any", "dialogue"), default="any")
    args = parser.parse_args()

    topology_path = args.cache_root / "topology.md"
    asset_catalog_path = args.asset_catalog or args.cache_root / "asset-catalog.json"
    character_introductions_path = args.character_introductions or args.cache_root / "character-introductions.json"
    spine_path = args.spine or args.cache_root / "emotional-spine.json"
    structure_output = args.structure_output or args.output.parent / "episode-structure.md"
    flowchart_output = args.flowchart_output or args.output.parent / "episode-flowchart.svg"
    try:
        public_dir = args.output.parent.resolve()
        cache_root = args.cache_root.resolve()
        expected_outputs = {
            "episode-script.md": args.output.resolve(),
            "episode-structure.md": structure_output.resolve(),
            "episode-flowchart.svg": flowchart_output.resolve(),
        }
        if cache_root == public_dir or public_dir in cache_root.parents:
            raise ValueError("缓存目录必须位于公开画布目录之外")
        if any(path.name != name for name, path in expected_outputs.items()):
            raise ValueError("三个公开输出必须使用固定文件名")
        if any(path.parent != public_dir for path in expected_outputs.values()):
            raise ValueError("三个公开输出必须位于同一公开目录")
        if public_dir.exists():
            extras = sorted(
                item.name for item in public_dir.iterdir()
                if item.resolve() not in set(expected_outputs.values())
            )
            if extras:
                raise ValueError("公开目录只能包含三个公开文件，发现：" + "、".join(extras))
        nodes = parse(topology_path)
        catalog = load_asset_catalog(asset_catalog_path)
        issues = validate_emotional_topology(
            topology_path,
            spine_path,
            None,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
        )
        pred = predecessors(nodes)
        expected_choice_count = sum(bool(node["choices"]) for node in nodes.values())
        scripts: list[str] = []
        synopses: dict[str, str] = {}
        digests: list[str] = []
        for node_id, node in nodes.items():
            path = args.cache_root / "episodes" / f"{node_id}.md"
            if not path.is_file():
                issues.append(f"缺少正文：{node_id}")
                continue
            text = path.read_text(encoding="utf-8").strip()
            episode_issues, synopsis = validate_episode(
                node_id,
                node,
                text,
                catalog,
                pred[node_id],
                len(nodes),
                expected_choice_count,
            )
            issues.extend(episode_issues)
            scripts.append(text)
            synopses[node_id] = synopsis
            digests.append(f"{node_id} {hashlib.sha256(text.encode()).hexdigest()}")
        issues.extend(
            validate_character_appearance_project(
                args.cache_root,
                nodes,
                catalog,
                character_introductions_path,
            )
        )
        issues.extend(verify_project(args.cache_root))
        issues.extend(validate_user_intent_project(args.cache_root))
        issues.extend(
            validate_change_scope(
                args.cache_root,
                args.baseline_root,
                list(nodes),
                set(args.allowed_changed),
                args.change_scope,
            )
        )
        if issues:
            print("FAIL")
            for issue in issues:
                print(f"- {issue}")
            return 1
        assembled = "\n\n---\n\n".join(scripts) + "\n"
        structure = build_structure(nodes, synopses)
        flowchart = build_flowchart(nodes)
        ET.fromstring(flowchart)
        if re.findall(r"^##\s+(episode-\d{3})", structure, re.MULTILINE) != list(nodes):
            raise ValueError("生成的 episode-structure.md 编号不一致")
        if set(re.findall(r'data-node-id="(episode-\d{3})"', flowchart)) != set(nodes):
            raise ValueError("生成的 episode-flowchart.svg 节点不完整")
        expected_choice_ids = {f"choice-{index:03d}" for index in range(1, expected_choice_count + 1)}
        actual_choice_ids = set(re.findall(r'data-choice-id="(choice-\d{3})"', flowchart))
        if actual_choice_ids != expected_choice_ids:
            raise ValueError("生成的 episode-flowchart.svg 选择节点不完整")
        grouped_atomic_write(
            [
                (args.output, assembled),
                (structure_output, structure),
                (flowchart_output, flowchart),
            ]
        )
        for path in (args.output, structure_output, flowchart_output):
            path.read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError, ET.ParseError) as error:
        print(f"FAIL: {error}")
        return 1

    print(f"PASS: {len(scripts)} episodes and {expected_choice_count} choices validated; three public files built and read back")
    for label, path in (("script", args.output), ("structure", structure_output), ("flowchart", flowchart_output)):
        print(f"{label} {hashlib.sha256(path.read_bytes()).hexdigest()} {path}")
    for digest in digests:
        print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
