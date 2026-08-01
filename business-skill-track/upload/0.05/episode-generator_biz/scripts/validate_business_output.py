#!/usr/bin/env python3
"""Validate the episode-generator business interface output."""

from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path
from typing import Any


TOP_FIELDS = ["分集结构", "分集列表"]
STRUCTURE_FIELDS = ["节点编号", "节点类型", "分集编号", "分集标题", "类型", "是否结局", "单集梗概", "来源分集编号", "选择问题", "选项列表", "后续节点编号列表"]
EPISODE_FIELDS = ["分集编号", "分集标题", "分集数", "选择数", "分集剧本", "剧本分析", "关联角色", "关联场景", "关联道具", "是否结局", "互动节点"]
SCRIPT_FIELDS = ["单集梗概", "完整剧本"]
ANALYSIS_FIELDS = ["本集冲突", "前置节点编号列表", "后续节点编号列表"]
INTERACTION_FIELDS = ["是否为分支节点", "是否有选择问题", "选择问题", "选项列表", "默认下一分集编号"]
OPTION_FIELDS = ["选项编号", "选项文字", "目标分集编号"]
EPISODE_ID = re.compile(r"episode-\d{3}")
CHOICE_ID = re.compile(r"choice-\d{3}")
DELIVERY_ID = re.compile(r"(?:episode|choice)-\d{3}")
SCENE_HEADING = re.compile(r"^【[^】·]+·[^】·]+·(?:内|外)】$")
ANNOUNCED_CHOICE = re.compile(r"(?:现在请选择|请(?:玩家)?做出选择|玩家请选择|你(?:会|将)如何选择|请选择以下)")


def exact_keys(value: Any, expected: list[str], label: str, issues: list[str]) -> bool:
    if not isinstance(value, dict):
        issues.append(f"{label}必须是对象")
        return False
    actual = list(value)
    if actual != expected:
        issues.append(f"{label}字段或顺序错误：{actual}")
        return False
    return True


def string_list(value: Any, label: str, issues: list[str], allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        issues.append(f"{label}必须是数组")
        return []
    if not allow_empty and not value:
        issues.append(f"{label}不得为空")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        issues.append(f"{label}必须只含非空字符串")
        return []
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        issues.append(f"{label}存在重复值")
    return normalized


def episode_ids(value: Any, label: str, issues: list[str]) -> list[str]:
    result = string_list(value, label, issues)
    if any(EPISODE_ID.fullmatch(item) is None for item in result):
        issues.append(f"{label}含非法分集编号")
    return result


def asset_catalog(path: Path | None, issues: list[str]) -> dict[str, set[str]] | None:
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        issues.append(f"资产索引不可读取：{error}")
        return None
    if not isinstance(data, dict) or data.get("contract_version") != "nextplay.episode-assets.v1":
        issues.append("资产索引合同错误")
        return None
    result: dict[str, set[str]] = {}
    for key in ("characters", "scenes", "props"):
        values = string_list(data.get(key), f"资产索引/{key}", issues)
        result[key] = set(values)
    return result


def normalized_dialogue_shape(script: str) -> str:
    return re.sub(r"^([^\n：]{1,20}：).*$", r"\1<DIALOGUE>", script, flags=re.MULTILINE)


def validate_opening_choice(script: str, issues: list[str]) -> None:
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


def validate_graph(
    order: list[str],
    successors: dict[str, list[str]],
    endings: set[str],
    issues: list[str],
) -> dict[str, list[str]]:
    incoming = {node_id: 0 for node_id in order}
    predecessors = {node_id: [] for node_id in order}
    for source in order:
        targets = successors[source]
        if len(targets) != len(set(targets)):
            issues.append(f"{source}后续节点重复")
        if source in targets:
            issues.append(f"{source}存在自环")
        if source in endings and targets:
            issues.append(f"{source}是结局但仍有后继")
        if source not in endings and not targets:
            issues.append(f"{source}不是结局但没有后继")
        for target in targets:
            if target not in incoming:
                issues.append(f"跳转目标不存在：{source}->{target}")
                continue
            incoming[target] += 1
            predecessors[target].append(source)
    roots = [node_id for node_id in order if incoming[node_id] == 0]
    if roots != ["episode-001"]:
        issues.append(f"入口不唯一或不是episode-001：{roots}")
    visited: set[str] = set()
    queue = deque(roots)
    while queue:
        node_id = queue.popleft()
        if node_id in visited or node_id not in successors:
            continue
        visited.add(node_id)
        queue.extend(successors[node_id])
    if visited != set(order):
        issues.append(f"存在不可达节点：{sorted(set(order) - visited)}")
    indegree = incoming.copy()
    queue = deque(node_id for node_id in order if indegree[node_id] == 0)
    count = 0
    while queue:
        node_id = queue.popleft()
        count += 1
        for target in successors[node_id]:
            if target in indegree:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
    if count != len(order):
        issues.append("分集拓扑存在循环")
    reverse = {node_id: [] for node_id in order}
    for source, targets in successors.items():
        for target in targets:
            if target in reverse:
                reverse[target].append(source)
    can_end = set(endings)
    queue = deque(endings)
    while queue:
        target = queue.popleft()
        for source in reverse[target]:
            if source not in can_end:
                can_end.add(source)
                queue.append(source)
    if can_end != set(order):
        issues.append(f"存在无法到达结局的节点：{sorted(set(order) - can_end)}")
    return predecessors


def validate(
    data: Any,
    catalog_path: Path | None,
    expected_endings: int | None,
    expected_formal: int | None,
    expected_failure: int | None,
    baseline: Any | None,
    allowed_changed: set[str],
    change_scope: str,
) -> list[str]:
    issues: list[str] = []
    if not exact_keys(data, TOP_FIELDS, "顶层", issues):
        return issues
    structures = data["分集结构"]
    episodes = data["分集列表"]
    if not isinstance(structures, list) or not structures:
        issues.append("分集结构必须是非空数组")
        return issues
    if not isinstance(episodes, list) or not episodes:
        issues.append("分集列表必须是非空数组")
        return issues

    delivery_order: list[str] = []
    episode_order: list[str] = []
    delivery_successors: dict[str, list[str]] = {}
    endings: set[str] = set()
    structure_by_node_id: dict[str, dict[str, Any]] = {}
    episode_structure_by_id: dict[str, dict[str, Any]] = {}
    choice_structure_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(structures):
        if not exact_keys(item, STRUCTURE_FIELDS, f"分集结构/{index}", issues):
            continue
        node_id = item["节点编号"]
        node_type = item["节点类型"]
        if not isinstance(node_id, str) or DELIVERY_ID.fullmatch(node_id) is None:
            issues.append(f"分集结构/{index}/节点编号非法")
            continue
        if node_id in structure_by_node_id:
            issues.append(f"分集结构节点编号重复：{node_id}")
            continue
        if node_type not in {"剧集节点", "选择节点"}:
            issues.append(f"{node_id}/节点类型非法")
            continue
        if not isinstance(item["是否结局"], bool):
            issues.append(f"{node_id}/是否结局必须为布尔值")
        targets = string_list(item["后续节点编号列表"], f"{node_id}/后续节点编号列表", issues)
        if any(DELIVERY_ID.fullmatch(target) is None for target in targets):
            issues.append(f"{node_id}/后续节点含非法编号")
        if not isinstance(item["选项列表"], list):
            issues.append(f"{node_id}/选项列表必须是数组")
        delivery_order.append(node_id)
        delivery_successors[node_id] = targets
        structure_by_node_id[node_id] = item
        if item["是否结局"] is True:
            endings.add(node_id)
        if node_type == "剧集节点":
            episode_id = item["分集编号"]
            if node_id != episode_id or not isinstance(episode_id, str) or EPISODE_ID.fullmatch(episode_id) is None:
                issues.append(f"{node_id}/剧集节点编号与分集编号不一致")
                continue
            for field in ("分集标题", "类型", "单集梗概"):
                if not isinstance(item[field], str) or not item[field].strip():
                    issues.append(f"{node_id}/{field}必须为非空字符串")
            if item["来源分集编号"] != "" or item["选择问题"] != "" or item["选项列表"] != []:
                issues.append(f"{node_id}/剧集节点不得携带选择节点内容")
            episode_order.append(node_id)
            episode_structure_by_id[node_id] = item
        else:
            if CHOICE_ID.fullmatch(node_id) is None:
                issues.append(f"{node_id}/选择节点编号非法")
            source = item["来源分集编号"]
            if item["分集编号"] != source or not isinstance(source, str) or EPISODE_ID.fullmatch(source) is None:
                issues.append(f"{node_id}/来源分集编号非法")
            if item["分集标题"] != "" or item["类型"] != "选择" or item["是否结局"] is not False or item["单集梗概"] != "":
                issues.append(f"{node_id}/选择节点含剧集内容")
            if not isinstance(item["选择问题"], str) or not item["选择问题"].strip():
                issues.append(f"{node_id}/选择问题为空")
            if len(targets) < 2 or any(EPISODE_ID.fullmatch(target) is None for target in targets):
                issues.append(f"{node_id}/选择节点必须指向至少两个剧集节点")
            option_targets: list[str] = []
            if isinstance(item["选项列表"], list):
                for option_index, option in enumerate(item["选项列表"]):
                    if not exact_keys(option, OPTION_FIELDS, f"{node_id}/选项/{option_index}", issues):
                        continue
                    if not isinstance(option["选项编号"], (str, int)) or isinstance(option["选项编号"], bool):
                        issues.append(f"{node_id}/选项编号类型非法")
                    if not isinstance(option["选项文字"], str) or not option["选项文字"].strip():
                        issues.append(f"{node_id}/选项文字为空")
                    if not isinstance(option["目标分集编号"], str) or EPISODE_ID.fullmatch(option["目标分集编号"]) is None:
                        issues.append(f"{node_id}/选项目标非法")
                    else:
                        option_targets.append(option["目标分集编号"])
            if option_targets != targets:
                issues.append(f"{node_id}/选项目标与后续节点不一致")
            choice_structure_by_id[node_id] = item
    expected_episode_order = [f"episode-{index:03d}" for index in range(1, len(episode_order) + 1)]
    if episode_order != expected_episode_order:
        issues.append(f"分集编号或顺序不连续：{episode_order}")
    expected_choice_order = [f"choice-{index:03d}" for index in range(1, len(choice_structure_by_id) + 1)]
    if list(choice_structure_by_id) != expected_choice_order:
        issues.append(f"选择节点编号或顺序不连续：{list(choice_structure_by_id)}")
    delivery_predecessors = validate_graph(delivery_order, delivery_successors, endings, issues)
    creative_successors: dict[str, list[str]] = {}
    for episode_id in episode_order:
        targets = delivery_successors.get(episode_id, [])
        if len(targets) == 1 and targets[0] in choice_structure_by_id:
            creative_successors[episode_id] = delivery_successors.get(targets[0], [])
        else:
            creative_successors[episode_id] = targets
    creative_predecessors = {episode_id: [] for episode_id in episode_order}
    for source, targets in creative_successors.items():
        for target in targets:
            if target in creative_predecessors:
                creative_predecessors[target].append(source)

    catalog = asset_catalog(catalog_path, issues)
    episode_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(episodes):
        if not exact_keys(item, EPISODE_FIELDS, f"分集列表/{index}", issues):
            continue
        node_id = item["分集编号"]
        if not isinstance(node_id, str) or node_id not in episode_structure_by_id:
            issues.append(f"分集列表/{index}/分集编号不存在于结构")
            continue
        if node_id in episode_by_id:
            issues.append(f"分集列表编号重复：{node_id}")
            continue
        episode_by_id[node_id] = item
        structure = episode_structure_by_id[node_id]
        if item["分集标题"] != structure["分集标题"]:
            issues.append(f"{node_id}/标题与结构不一致")
        if (
            not isinstance(item["分集数"], int)
            or isinstance(item["分集数"], bool)
            or item["分集数"] != len(episode_order)
        ):
            issues.append(f"{node_id}/分集数必须等于剧集节点总数{len(episode_order)}")
        if (
            not isinstance(item["选择数"], int)
            or isinstance(item["选择数"], bool)
            or item["选择数"] != len(choice_structure_by_id)
        ):
            issues.append(f"{node_id}/选择数必须等于选择节点总数{len(choice_structure_by_id)}")
        if item["是否结局"] != structure["是否结局"] or not isinstance(item["是否结局"], bool):
            issues.append(f"{node_id}/结局标记与结构不一致")
        if not exact_keys(item["分集剧本"], SCRIPT_FIELDS, f"{node_id}/分集剧本", issues):
            continue
        if not exact_keys(item["剧本分析"], ANALYSIS_FIELDS, f"{node_id}/剧本分析", issues):
            continue
        if not exact_keys(item["互动节点"], INTERACTION_FIELDS, f"{node_id}/互动节点", issues):
            continue
        script = item["分集剧本"]["完整剧本"]
        synopsis = item["分集剧本"]["单集梗概"]
        if not isinstance(synopsis, str) or not synopsis.strip() or synopsis != structure["单集梗概"]:
            issues.append(f"{node_id}/单集梗概为空或与结构不一致")
        if not isinstance(script, str) or not script.strip():
            issues.append(f"{node_id}/完整剧本为空")
            script = ""
        scene_lines = [line.strip() for line in script.splitlines() if line.strip().startswith("【")]
        if not scene_lines:
            issues.append(f"{node_id}/缺少场次标题")
        elif any(SCENE_HEADING.fullmatch(line) is None for line in scene_lines):
            issues.append(f"{node_id}/场次标题格式错误")
        if re.search(r"^\s*(?:△|出场：)", script, re.MULTILINE):
            issues.append(f"{node_id}/含禁用正文格式")
        if re.search(r"^[^\n：]{1,20}：\s*[“\"]", script, re.MULTILINE):
            issues.append(f"{node_id}/对白使用了台词引号")
        if not isinstance(item["剧本分析"]["本集冲突"], str) or not item["剧本分析"]["本集冲突"].strip():
            issues.append(f"{node_id}/本集冲突为空")
        prev = episode_ids(item["剧本分析"]["前置节点编号列表"], f"{node_id}/前置节点", issues)
        nxt = episode_ids(item["剧本分析"]["后续节点编号列表"], f"{node_id}/后续节点", issues)
        if prev != creative_predecessors.get(node_id, []):
            issues.append(f"{node_id}/前置节点与拓扑不一致")
        if nxt != creative_successors[node_id]:
            issues.append(f"{node_id}/后续节点与拓扑不一致")
        for field, catalog_key in (("关联角色", "characters"), ("关联场景", "scenes"), ("关联道具", "props")):
            values = string_list(item[field], f"{node_id}/{field}", issues)
            if catalog is not None:
                unknown = sorted(set(values) - catalog[catalog_key])
                if unknown:
                    issues.append(f"{node_id}/{field}含非正式资产：{unknown}")
        interaction = item["互动节点"]
        for field in ("是否为分支节点", "是否有选择问题"):
            if not isinstance(interaction[field], bool):
                issues.append(f"{node_id}/{field}必须为布尔值")
        options = interaction["选项列表"]
        if not isinstance(options, list):
            issues.append(f"{node_id}/选项列表必须是数组")
            options = []
        numbers: list[Any] = []
        targets: list[str] = []
        for option_index, option in enumerate(options):
            if not exact_keys(option, OPTION_FIELDS, f"{node_id}/选项/{option_index}", issues):
                continue
            numbers.append(option["选项编号"])
            if not isinstance(option["选项编号"], (str, int)) or isinstance(option["选项编号"], bool):
                issues.append(f"{node_id}/选项编号类型非法")
            if not isinstance(option["选项文字"], str) or not option["选项文字"].strip():
                issues.append(f"{node_id}/选项文字为空")
            target = option["目标分集编号"]
            if not isinstance(target, str) or EPISODE_ID.fullmatch(target) is None:
                issues.append(f"{node_id}/选项目标非法")
            else:
                targets.append(target)
        is_branch = interaction["是否为分支节点"] is True
        has_question = interaction["是否有选择问题"] is True
        question = interaction["选择问题"]
        default_next = interaction["默认下一分集编号"]
        if is_branch != has_question:
            issues.append(f"{node_id}/分支标记与问题标记不一致")
        if is_branch:
            if structure["类型"] != "分支剧集":
                issues.append(f"{node_id}/分支剧集类型必须为分支剧集")
            if node_id == "episode-001":
                validate_opening_choice(script, issues)
            if len(options) < 2 or len(set(targets)) < 2:
                issues.append(f"{node_id}/选择出口不足两个不同目标")
            if len(numbers) != len(set(map(str, numbers))):
                issues.append(f"{node_id}/选项编号重复")
            if set(targets) != set(creative_successors[node_id]):
                issues.append(f"{node_id}/选项目标与拓扑后继不一致")
            if not isinstance(question, str) or not question.strip():
                issues.append(f"{node_id}/选择问题为空")
            if default_next not in creative_successors[node_id]:
                issues.append(f"{node_id}/默认下一集不在选择后继中")
            delivery_targets = delivery_successors.get(node_id, [])
            choice = choice_structure_by_id.get(delivery_targets[0]) if len(delivery_targets) == 1 else None
            if choice is None:
                issues.append(f"{node_id}/分支剧集未连接唯一选择节点")
            else:
                if choice["来源分集编号"] != node_id:
                    issues.append(f"{node_id}/选择节点来源不一致")
                if choice["选择问题"] != question or choice["选项列表"] != options:
                    issues.append(f"{node_id}/选择节点内容与互动节点不一致")
                if delivery_predecessors.get(choice["节点编号"], []) != [node_id]:
                    issues.append(f"{choice['节点编号']}/选择节点必须且只能有一个来源剧集")
        else:
            if structure["类型"] == "分支剧集":
                issues.append(f"{node_id}/非分支剧集类型错误")
            if options:
                issues.append(f"{node_id}/非分支节点含选项")
            if question not in {"", "无"}:
                issues.append(f"{node_id}/非分支节点含选择问题")
            expected_default = "无" if node_id in endings else (creative_successors[node_id][0] if len(creative_successors[node_id]) == 1 else "无")
            if default_next != expected_default:
                issues.append(f"{node_id}/默认下一集错误")
            if any(target in choice_structure_by_id for target in delivery_successors.get(node_id, [])):
                issues.append(f"{node_id}/非分支剧集错误连接选择节点")

    if list(episode_by_id) != episode_order:
        issues.append("分集列表编号或顺序与分集结构不一致")
    total = len(endings)
    formal = sum(1 for item in structures if item.get("是否结局") is True and item.get("类型") == "正式结局")
    failure = sum(1 for item in structures if item.get("是否结局") is True and item.get("类型") == "失败小结局")
    if expected_endings is not None and total != expected_endings:
        issues.append(f"结局数量错误：期望{expected_endings}，实际{total}")
    if expected_formal is not None and formal != expected_formal:
        issues.append(f"正式结局数量错误：期望{expected_formal}，实际{formal}")
    if expected_failure is not None and failure != expected_failure:
        issues.append(f"失败小结局数量错误：期望{expected_failure}，实际{failure}")

    if baseline is not None:
        if not isinstance(baseline, dict) or list(baseline) != TOP_FIELDS:
            issues.append("修改基线不符合业务接口")
        else:
            if baseline.get("分集结构") != structures:
                issues.append("局部修改期间冻结拓扑或结构发生变化")
            base_episodes = {
                item.get("分集编号"): item
                for item in baseline.get("分集列表", [])
                if isinstance(item, dict)
            }
            if not allowed_changed:
                issues.append("使用修改基线时必须声明允许变化的分集")
            for node_id, current in episode_by_id.items():
                previous = base_episodes.get(node_id)
                if previous is None:
                    issues.append(f"修改基线缺少分集：{node_id}")
                    continue
                if node_id not in allowed_changed and current != previous:
                    issues.append(f"未授权分集发生变化：{node_id}")
                if node_id in allowed_changed and change_scope == "dialogue":
                    current_copy = json.loads(json.dumps(current, ensure_ascii=False))
                    previous_copy = json.loads(json.dumps(previous, ensure_ascii=False))
                    current_script = current_copy["分集剧本"]["完整剧本"]
                    previous_script = previous_copy["分集剧本"]["完整剧本"]
                    current_copy["分集剧本"]["完整剧本"] = normalized_dialogue_shape(current_script)
                    previous_copy["分集剧本"]["完整剧本"] = normalized_dialogue_shape(previous_script)
                    if current_copy != previous_copy:
                        issues.append(f"台词修改越过对白范围：{node_id}")
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--asset-catalog", type=Path)
    parser.add_argument("--expected-endings", type=int)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--allowed-changed", action="append", default=[])
    parser.add_argument("--change-scope", choices=("any", "dialogue"), default="any")
    args = parser.parse_args()
    try:
        data = json.loads(args.output.read_text(encoding="utf-8"))
        baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
        issues = validate(
            data,
            args.asset_catalog,
            args.expected_endings,
            args.expected_formal,
            args.expected_failure,
            baseline,
            set(args.allowed_changed),
            args.change_scope,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"FAIL: {error}")
        return 1
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    count = len(data["分集列表"])
    print(f"PASS: {count} episodes; business interface, topology, fields, assets, endings, and change scope verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
