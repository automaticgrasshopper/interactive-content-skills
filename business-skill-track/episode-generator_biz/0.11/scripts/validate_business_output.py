#!/usr/bin/env python3
"""Validate the episode-generator business interface output."""

from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path
from typing import Any


TOP_FIELDS = ["分集列表"]
EPISODE_FIELDS = ["分集编号", "分集标题", "分集数", "分集剧本", "剧本分析", "关联角色", "关联场景", "关联道具", "是否结局", "选择节点", "互动节点"]
SCRIPT_FIELDS = ["完整剧本", "单集梗概"]
ANALYSIS_FIELDS = ["本集冲突", "前置节点编号列表", "后续节点编号列表"]
CHOICE_FIELDS = ["是否为选择节点", "是否有选择问题", "选择节点编号", "选择问题", "选项列表"]
INTERACTION_FIELDS = ["是否为互动节点", "互动节点编号", "后边是否接选择节点", "后续选择节点编号"]
OPTION_FIELDS = ["选项编号", "选项文字", "目标互动节点编号"]
EPISODE_ID = re.compile(r"episode-\d{3}")
CHOICE_ID = re.compile(r"choice-\d{3}")
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


def string_list(value: Any, label: str, issues: list[str]) -> list[str]:
    if not isinstance(value, list):
        issues.append(f"{label}必须是数组")
        return []
    if any(not isinstance(item, str) or not item.strip() for item in value):
        issues.append(f"{label}必须只含非空字符串")
        return []
    result = [item.strip() for item in value]
    if len(result) != len(set(result)):
        issues.append(f"{label}存在重复值")
    return result


def episode_ids(value: Any, label: str, issues: list[str]) -> list[str]:
    result = string_list(value, label, issues)
    if any(EPISODE_ID.fullmatch(item) is None for item in result):
        issues.append(f"{label}含非法互动节点编号")
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
        result[key] = set(string_list(data.get(key), f"资产索引/{key}", issues))
    return result


def normalized_dialogue_shape(script: str) -> str:
    return re.sub(r"^([^\n：]{1,20}：).*$", r"\1<DIALOGUE>", script, flags=re.MULTILINE)


def validate_opening_choice(script: str, issues: list[str]) -> None:
    lines = [line.strip() for line in script.splitlines() if line.strip() and SCENE_HEADING.fullmatch(line.strip()) is None]
    compact = re.sub(r"\s+", "", "\n".join(lines))
    if len(compact) < 60:
        issues.append("episode-001/首集选择前实质剧情不足60字符")
    if len([line for line in lines if len(re.sub(r"\s+", "", line)) >= 4]) < 2:
        issues.append("episode-001/首集选择前实质剧情不足两行")
    if ANNOUNCED_CHOICE.search(script):
        issues.append("episode-001/正文用制作话术直接宣布选择")


def validate_graph(order: list[str], successors: dict[str, list[str]], endings: set[str], issues: list[str]) -> dict[str, list[str]]:
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
                issues.append(f"目标互动节点不存在：{source}->{target}")
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
        issues.append(f"存在不可达互动节点：{sorted(set(order) - visited)}")
    indegree = incoming.copy()
    queue = deque(node for node in order if indegree[node] == 0)
    count = 0
    while queue:
        source = queue.popleft()
        count += 1
        for target in successors[source]:
            if target in indegree:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
    if count != len(order):
        issues.append("互动拓扑存在循环")
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
        issues.append(f"存在无法到达结局的互动节点：{sorted(set(order) - can_end)}")
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
    episodes = data["分集列表"]
    if not isinstance(episodes, list) or not episodes:
        return ["分集列表必须是非空数组"]
    expected_order = [f"episode-{index:03d}" for index in range(1, len(episodes) + 1)]
    order: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    successors: dict[str, list[str]] = {}
    endings: set[str] = set()
    seen_choices: list[str] = []
    catalog = asset_catalog(catalog_path, issues)
    for index, item in enumerate(episodes):
        if not exact_keys(item, EPISODE_FIELDS, f"分集列表/{index}", issues):
            continue
        node_id = item["分集编号"]
        if not isinstance(node_id, str) or EPISODE_ID.fullmatch(node_id) is None:
            issues.append(f"分集列表/{index}/分集编号非法")
            continue
        if node_id in by_id:
            issues.append(f"互动节点编号重复：{node_id}")
            continue
        order.append(node_id)
        by_id[node_id] = item
        if not isinstance(item["分集标题"], str) or not item["分集标题"].strip():
            issues.append(f"{node_id}/分集标题为空")
        if not isinstance(item["分集数"], int) or isinstance(item["分集数"], bool) or item["分集数"] != len(episodes):
            issues.append(f"{node_id}/分集数必须等于互动节点总数{len(episodes)}")
        if not isinstance(item["是否结局"], bool):
            issues.append(f"{node_id}/是否结局必须为布尔值")
        elif item["是否结局"]:
            endings.add(node_id)
        if not exact_keys(item["分集剧本"], SCRIPT_FIELDS, f"{node_id}/分集剧本", issues):
            continue
        if not exact_keys(item["剧本分析"], ANALYSIS_FIELDS, f"{node_id}/剧本分析", issues):
            continue
        if not exact_keys(item["选择节点"], CHOICE_FIELDS, f"{node_id}/选择节点", issues):
            continue
        if not exact_keys(item["互动节点"], INTERACTION_FIELDS, f"{node_id}/互动节点", issues):
            continue
        script = item["分集剧本"]["完整剧本"]
        synopsis = item["分集剧本"]["单集梗概"]
        if not isinstance(script, str) or not script.strip():
            issues.append(f"{node_id}/完整剧本为空")
            script = ""
        if not isinstance(synopsis, str) or not synopsis.strip():
            issues.append(f"{node_id}/单集梗概为空")
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
        successors[node_id] = episode_ids(item["剧本分析"]["后续节点编号列表"], f"{node_id}/后续节点", issues)
        episode_ids(item["剧本分析"]["前置节点编号列表"], f"{node_id}/前置节点", issues)
        for field, key in (("关联角色", "characters"), ("关联场景", "scenes"), ("关联道具", "props")):
            values = string_list(item[field], f"{node_id}/{field}", issues)
            if catalog is not None:
                unknown = sorted(set(values) - catalog[key])
                if unknown:
                    issues.append(f"{node_id}/{field}含非正式资产：{unknown}")
        interaction = item["互动节点"]
        choice = item["选择节点"]
        if interaction["是否为互动节点"] is not True or interaction["互动节点编号"] != node_id:
            issues.append(f"{node_id}/互动节点身份不一致")
        is_choice_record = choice["是否为选择节点"] is True
        has_choice = choice["是否有选择问题"] is True
        if not isinstance(choice["是否为选择节点"], bool) or not isinstance(choice["是否有选择问题"], bool) or not isinstance(interaction["后边是否接选择节点"], bool):
            issues.append(f"{node_id}/节点标记必须为布尔值")
        if is_choice_record:
            issues.append(f"{node_id}/分集记录不得同时标记为选择节点")
        if has_choice != (interaction["后边是否接选择节点"] is True):
            issues.append(f"{node_id}/选择存在标记与互动连线不一致")
        options = choice["选项列表"] if isinstance(choice["选项列表"], list) else []
        if not isinstance(choice["选项列表"], list):
            issues.append(f"{node_id}/选项列表必须为数组")
        if has_choice:
            choice_id = choice["选择节点编号"]
            if not isinstance(choice_id, str) or CHOICE_ID.fullmatch(choice_id) is None:
                issues.append(f"{node_id}/选择节点编号非法")
            else:
                seen_choices.append(choice_id)
            if interaction["后续选择节点编号"] != choice_id:
                issues.append(f"{node_id}/后续选择节点编号不一致")
            if not isinstance(choice["选择问题"], str) or not choice["选择问题"].strip():
                issues.append(f"{node_id}/选择问题为空")
            numbers: list[str] = []
            targets: list[str] = []
            for option_index, option in enumerate(options):
                if not exact_keys(option, OPTION_FIELDS, f"{node_id}/选项/{option_index}", issues):
                    continue
                numbers.append(str(option["选项编号"]))
                if not isinstance(option["选项编号"], (str, int)) or isinstance(option["选项编号"], bool):
                    issues.append(f"{node_id}/选项编号类型非法")
                if not isinstance(option["选项文字"], str) or not option["选项文字"].strip():
                    issues.append(f"{node_id}/选项文字为空")
                target = option["目标互动节点编号"]
                if not isinstance(target, str) or EPISODE_ID.fullmatch(target) is None:
                    issues.append(f"{node_id}/选项目标互动节点非法")
                else:
                    targets.append(target)
            if len(options) < 2 or len(set(targets)) < 2:
                issues.append(f"{node_id}/选择出口不足两个不同互动节点")
            if len(numbers) != len(set(numbers)):
                issues.append(f"{node_id}/选项编号重复")
            if targets != successors[node_id]:
                issues.append(f"{node_id}/选项目标与后续互动节点不一致")
            if node_id == "episode-001":
                validate_opening_choice(script, issues)
        else:
            if choice["选择节点编号"] != "无" or choice["选择问题"] not in {"", "无"} or options:
                issues.append(f"{node_id}/非选择节点含选择信息")
            if interaction["后续选择节点编号"] != "无":
                issues.append(f"{node_id}/非选择互动节点仍连接选择节点")
    if order != expected_order:
        issues.append(f"互动节点编号或顺序不连续：{order}")
    expected_choices = [f"choice-{index:03d}" for index in range(1, len(seen_choices) + 1)]
    if seen_choices != expected_choices:
        issues.append(f"选择节点编号或顺序不连续：{seen_choices}")
    predecessors = validate_graph(order, successors, endings, issues) if order == expected_order else {node_id: [] for node_id in order}
    for node_id, item in by_id.items():
        actual_prev = item["剧本分析"]["前置节点编号列表"] if isinstance(item.get("剧本分析"), dict) else []
        if actual_prev != predecessors.get(node_id, []):
            issues.append(f"{node_id}/前置节点与拓扑不一致")
    if expected_endings is not None and len(endings) != expected_endings:
        issues.append(f"结局总数错误：期望{expected_endings}，实际{len(endings)}")
    # 正式／失败结局分类属于私有拓扑字段，已由
    # validate_emotional_topology.py 在业务投射前强验证；最新版公开十一字段
    # 只保留“是否结局”，这里不以标题猜测结局类型。
    if baseline is not None:
        if not isinstance(baseline, dict) or not isinstance(baseline.get("分集列表"), list):
            issues.append("基线格式错误")
        else:
            baseline_by_id = {item.get("分集编号"): item for item in baseline["分集列表"] if isinstance(item, dict)}
            if set(baseline_by_id) != set(by_id):
                issues.append("局部修改期间互动拓扑节点集合发生变化")
            for node_id, current in by_id.items():
                previous = baseline_by_id.get(node_id)
                if previous is None:
                    continue
                if node_id not in allowed_changed and current != previous:
                    issues.append(f"未授权分集发生变化：{node_id}")
                elif node_id in allowed_changed and change_scope == "dialogue":
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
    parser.add_argument("input", type=Path)
    parser.add_argument("--asset-catalog", type=Path)
    parser.add_argument("--expected-endings", type=int)
    parser.add_argument("--expected-formal", type=int)
    parser.add_argument("--expected-failure", type=int)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--allowed-changed", action="append", default=[])
    parser.add_argument("--change-scope", choices=("any", "dialogue"), default="any")
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL：{error}")
        return 1
    issues = validate(data, args.asset_catalog, args.expected_endings, args.expected_formal, args.expected_failure, baseline, set(args.allowed_changed), args.change_scope)
    if issues:
        for issue in issues:
            print(f"FAIL：{issue}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
