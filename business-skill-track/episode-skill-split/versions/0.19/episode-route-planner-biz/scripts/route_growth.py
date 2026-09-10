#!/usr/bin/env python3
"""Replay-checked, one-frontier-at-a-time route construction.

The hash chain detects inconsistent edits; it is not a permission boundary or a
signature. A writer who can replace every local input can rebuild a valid chain.
Narrative truth and the quality of a merge remain semantic review obligations.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import heapq
import json
import os
import re
import secrets
from pathlib import Path
import tempfile
from typing import Any

from route_contract import (
    CAPABILITY_ID, CONTRACT_VERSION as ROUTE_VERSION, ENDING_TYPES,
    MATERIAL_FIELDS, SCRIPT_ONLY_TERMS, expected_indexes, non_placeholder,
    string_list, validate as validate_route,
)

LEGACY_VERSION = "nextplay.route-growth-state.v1"
CONTRACT_VERSION = "nextplay.route-growth-state.v2"
UPSTREAM_FILES = (
    "user-request.md", "user-intent-lock.json", "creative-brief.json",
    "complete-story.json", "mainline-decomposition.json",
    "mainline-emotional-movement.json", "decision-fissure-audit.json",
)
STATE_FILE = "growth-state.json"
CANDIDATE_FILE = "route-candidate.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def serialized(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"重复JSON字段：{key}")
        value[key] = item
    return value


def _read(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"JSON数值非法：{value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                      parse_constant=reject_constant)


def _keys(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label}字段错误；只接受：{','.join(sorted(fields))}")


def _text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}必须是非空字符串")


def _atomic(path: Path, value: Any) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(serialized(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def _lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".route-growth.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _upstream(root: Path) -> tuple[dict[str, str], dict[str, Any], dict[str, str]]:
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in UPSTREAM_FILES}
    values = {name: _read(root / name) for name in UPSTREAM_FILES if name.endswith(".json")}
    brief = values["creative-brief.json"]
    if not isinstance(brief, dict):
        raise ValueError("creative-brief必须为对象")
    manifest = brief.get("manifest.json", {})
    if not isinstance(manifest, dict):
        raise ValueError("creative-brief/manifest.json必须为对象")
    project = brief.get("project_id", manifest.get("project_id"))
    if brief.get("project_id") and manifest.get("project_id") and brief["project_id"] != manifest["project_id"]:
        raise ValueError("creative-brief项目身份冲突")
    identity = {"project_id": project, "route_id": brief.get("route_id", "route-main"),
                "route_version": brief.get("route_version", "1")}
    for field, value in identity.items():
        _text(value, field)
    return hashes, values, identity


def _references(values: dict[str, Any]) -> tuple[set[str], set[str]]:
    def ids(filename: str, collection: str, field: str) -> set[str]:
        value = values[filename]
        items = value.get(collection) if isinstance(value, dict) else None
        if not isinstance(items, list) or not items:
            raise ValueError(f"{filename}/{collection}必须是非空数组")
        result: set[str] = set()
        for item in items:
            key = item.get(field) if isinstance(item, dict) else None
            _text(key, f"{filename}/{field}")
            if key in result:
                raise ValueError(f"{filename}/{field}重复：{key}")
            result.add(key)
        return result
    return (ids("mainline-decomposition.json", "mainline_segments", "segment_id"),
            ids("mainline-emotional-movement.json", "emotional_movements", "movement_id"))


def _node(value: Any, segment_ids: set[str], movement_ids: set[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError("一步必须新增且仅新增一个节点对象")
    fields = {"kind", "title", "route_material", "ending_type", "emotional_movement_ids"}
    if "mainline_segment_id" in value:
        fields.add("mainline_segment_id")
    if value.get("kind") == "choice":
        fields.update({"question", "options"})
        if "mainline_option_index" in value:
            fields.add("mainline_option_index")
    _keys(value, fields, "当前节点（不得输入正式图字段、后续目标或整条分支）")
    kind = value["kind"]
    if kind not in {"scene", "choice", "ending"}:
        raise ValueError("kind只允许scene/choice/ending")
    if not isinstance(value["title"], str) or not non_placeholder(value["title"], 2):
        raise ValueError("节点标题过短或占位")
    if (kind == "ending" and value["ending_type"] not in ENDING_TYPES) or (kind != "ending" and value["ending_type"] is not None):
        raise ValueError("ending_type与kind不一致")
    material = value["route_material"]
    _keys(material, MATERIAL_FIELDS, "route_material")
    for field, minimum in (("单集梗概", 24), ("本集冲突", 10), ("stop_boundary", 12)):
        if not isinstance(material[field], str) or not non_placeholder(material[field], minimum):
            raise ValueError(f"route_material/{field}过短或占位")
    for field in ("entry_state", "state_changes"):
        if not isinstance(material[field], dict):
            raise ValueError(f"route_material/{field}必须为对象")
    for field in ("allowed_characters", "allowed_scenes", "allowed_props"):
        if not string_list(material[field]):
            raise ValueError(f"route_material/{field}必须为无重复字符串数组")
    if any(term in json.dumps(value, ensure_ascii=False) for term in SCRIPT_ONLY_TERMS):
        raise ValueError("当前节点含剧本侧内容字段")
    movements = value["emotional_movement_ids"]
    if not string_list(movements) or not movements or not set(movements) <= movement_ids:
        raise ValueError("emotional_movement_ids未绑定冻结输入")
    if value.get("mainline_segment_id") is not None and value["mainline_segment_id"] not in segment_ids:
        raise ValueError("mainline_segment_id未绑定冻结输入")
    if kind == "choice":
        if not isinstance(value["question"], str) or not non_placeholder(value["question"], 4):
            raise ValueError("选择问题过短或占位")
        options = value["options"]
        if not isinstance(options, list) or len(options) < 2 or any(not isinstance(option, str) or len(option.strip()) < 2 for option in options):
            raise ValueError("选择只能提交至少两个互斥动作文字，不得提供目标")
        if len({option.strip() for option in options}) != len(options):
            raise ValueError("选择动作文字必须互异")
        if "mainline_option_index" in value and (type(value["mainline_option_index"]) is not int or
                not 0 <= value["mainline_option_index"] < len(options)):
            raise ValueError("mainline_option_index必须是当前主线选项的零基索引")


def _reaches(edges: list[dict[str, Any]], source: str, target: str) -> bool:
    pending, seen = [source], set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(edge["target_node_id"] for edge in edges if edge["source_node_id"] == node)
    return False


def _repair_policy(graph, submission, values, root):
    action = submission.get("action", {}) if isinstance(submission, dict) else {}
    if not isinstance(action, dict) or action.get("type") != "repair":
        return
    old = next((n for n in graph["nodes"] if n["node_id"] == action.get("target_node_id")), None)
    value = action.get("node", {})
    if old and isinstance(value, dict) and old["kind"] != value.get("kind"):
        intent = values["user-intent-lock.json"]
        forbidden = re.search(r"(?:不要|不设|不需要|没有|无)(?:任何)?小结局", (root / "user-request.md").read_text())
        if forbidden or intent.get("shape_mode") == "exact" or any(v is not None for v in intent.get("hard_counts", {}).values()):
            raise ValueError("用户锁定形状、数量或禁用小结局时保留拓扑，使用内容修正")


def _repair(graph, action, segment_ids, movement_ids):
    _keys(action, {"type", "target_node_id", "node", "reason"}, "局部修正")
    _text(action["reason"], "修正原因与影响范围")
    target = action["target_node_id"]
    old = next((n for n in graph["nodes"] if n["node_id"] == target), None)
    if old is None:
        raise ValueError("修正目标必须是当前有效节点")
    value = action["node"]
    _node(value, segment_ids, movement_ids)
    closing = old["kind"] != "ending" and value["kind"] == "ending"
    if closing:
        if old.get("branch_depth", 0) == 0 or old.get("mainline_segment_id"):
            raise ValueError("主线不能截断为小结局；请局部修正内容并保留主线连接")
        if value["ending_type"] != "small":
            raise ValueError("支线局部收束须为有因果的小结局")
    elif old["kind"] == "ending" and value["kind"] == "scene":
        # A premature ending can resume locally without rebuilding its ancestors.
        graph["frontier_serial"] += 1
        frontier = {"frontier_id": f"frontier-{graph['frontier_serial']:06d}",
                    "source_node_id": target, "option_index": None, "option_text": None}
        for field in ("branch_depth", "return_bias", "bias_origin_frontier_id"):
            if field in old:
                frontier[field] = old[field]
        graph["frontiers"].append(frontier)
    elif value["kind"] != old["kind"]:
        raise ValueError("类型修正仅支持支线收束为小结局，或过早结局恢复为剧情节点")
    if bool(value.get("mainline_segment_id")) != bool(old.get("mainline_segment_id")) or value.get("mainline_option_index") != old.get("mainline_option_index"):
        raise ValueError("修正不能改变主线身份")
    segment = value.get("mainline_segment_id")
    if segment and any(n["node_id"] != target and n.get("mainline_segment_id") == segment for n in graph["nodes"]):
        raise ValueError("修正不能重复消费主线切片")
    if old["kind"] == "choice" and not closing and len(value["options"]) != len(old["options"]):
        raise ValueError("修正选择时须保留选项数量、顺序和连接")
    if old.get("branch_depth", 0) and value["ending_type"] == "main":
        raise ValueError("支线修正不能改标主结局")
    replacement = {"node_id": target, **deepcopy(value)}
    for field in ("branch_depth", "return_bias", "bias_origin_frontier_id"):
        if field in old:
            replacement[field] = old[field]
    graph["nodes"][graph["nodes"].index(old)] = replacement
    if value["kind"] == "choice":
        for frontier in graph["frontiers"]:
            if frontier["source_node_id"] == target:
                frontier["option_text"] = value["options"][frontier["option_index"]]
    if closing:
        graph["edges"] = [e for e in graph["edges"] if e["source_node_id"] != target]
        entry = graph["nodes"][0]["node_id"]
        reachable = {n["node_id"] for n in graph["nodes"] if _reaches(graph["edges"], entry, n["node_id"])}
        removed = [n for n in graph["nodes"] if n["node_id"] not in reachable]
        if any(n.get("branch_depth", 0) == 0 or n.get("mainline_segment_id") for n in removed):
            raise ValueError("局部收束不能移除主线")
        graph["nodes"] = [n for n in graph["nodes"] if n["node_id"] in reachable]
        graph["edges"] = [e for e in graph["edges"] if e["source_node_id"] in reachable and e["target_node_id"] in reachable]
        graph["frontiers"] = [f for f in graph["frontiers"] if f["source_node_id"] in reachable and f["source_node_id"] != target]


def _advance(graph: dict[str, Any], submission: Any, expected_hash: str,
             segment_ids: set[str], movement_ids: set[str]) -> None:
    _keys(submission, {"expected_state_hash", "frontier_id", "action"}, "单步提交")
    if submission["expected_state_hash"] != expected_hash:
        raise ValueError("旧状态：expected_state_hash与当前state_hash不一致")
    if isinstance(submission["action"], dict) and submission["action"].get("type") == "repair":
        if submission["frontier_id"] is not None:
            raise ValueError("修正提交frontier_id必须为null，不消费其他待推进项")
        _repair(graph, submission["action"], segment_ids, movement_ids)
        return
    if not graph["frontiers"]:
        raise ValueError("全部前沿已关闭，不能继续append")
    frontier = graph["frontiers"][0]
    if submission["frontier_id"] != frontier["frontier_id"]:
        raise ValueError("必须消费status指定的唯一FIFO前沿；拒绝跳步或已关闭前沿")
    action = submission["action"]
    if not isinstance(action, dict):
        raise ValueError("action必须是一个对象，拒绝批量步骤")
    kind = action.get("type")
    if kind == "node":
        _keys(action, {"type", "node"}, "新增一步")
        value = action["node"]
        _node(value, segment_ids, movement_ids)
        segment = value.get("mainline_segment_id")
        if segment and any(node.get("mainline_segment_id") == segment for node in graph["nodes"]):
            raise ValueError("同一主线切片不得被重复消费")
        graph["node_serial"] += 1
        target = f"growth-{graph['node_serial']:06d}"
        graph["nodes"].append({"node_id": target, **deepcopy(value)})
    elif kind == "merge":
        _keys(action, {"type", "target_node_id", "reason"}, "回汇一步")
        target = action["target_node_id"]
        if not isinstance(target, str) or target not in {node["node_id"] for node in graph["nodes"]}:
            raise ValueError("回汇必须指向已存在节点，拒绝未来目标")
        if frontier["source_node_id"] is None:
            raise ValueError("入口前沿不能回汇")
        _keys(action["reason"], {"current_facts", "shared_task"}, "回汇原因")
        for field in ("current_facts", "shared_task"):
            _text(action["reason"][field], f"回汇原因/{field}")
        if _reaches(graph["edges"], target, frontier["source_node_id"]):
            raise ValueError("回汇会产生循环")
    else:
        raise ValueError("一步action.type只允许node或merge")
    source = frontier["source_node_id"]
    if source is not None:
        if any(edge["source_node_id"] == source and edge["target_node_id"] == target for edge in graph["edges"]):
            raise ValueError("同一选择的选项必须指向不同目标")
        graph["edges"].append({"source_node_id": source, "target_node_id": target,
                               "option_index": frontier["option_index"]})
    graph["frontiers"].pop(0)
    if kind == "node" and value["kind"] != "ending":
        slots = list(range(len(value["options"]))) if value["kind"] == "choice" else [None]
        for slot in slots:
            graph["frontier_serial"] += 1
            graph["frontiers"].append({"frontier_id": f"frontier-{graph['frontier_serial']:06d}",
                                       "source_node_id": target, "option_index": slot,
                                       "option_text": value["options"][slot] if slot is not None else None})


def _initial_graph(version: str) -> dict[str, Any]:
    frontier = {"frontier_id": "frontier-000001", "source_node_id": None,
                "option_index": None, "option_text": None}
    if version == CONTRACT_VERSION:
        frontier.update(branch_depth=0, return_bias=None, bias_origin_frontier_id=None)
    return {"nodes": [], "edges": [], "node_serial": 0, "frontier_serial": 1, "frontiers": [frontier]}


def _advance_with_bias(graph: dict[str, Any], submission: Any, expected_hash: str,
                       segment_ids: set[str], movement_ids: set[str],
                       draws: Any, enabled: bool, *, creating: bool = False) -> list[dict[str, Any]]:
    # Validate the entire submitted action before obtaining any new random value.
    before = deepcopy(graph["frontiers"][0]) if graph["frontiers"] else None
    serial = graph["frontier_serial"]
    _advance(graph, submission, expected_hash, segment_ids, movement_ids)
    action = submission["action"]
    generated: list[dict[str, Any]] = []
    if action["type"] == "repair":
        if not creating and draws != []:
            raise ValueError("修正不能重抽签")
        return []
    if action["type"] == "node":
        node = graph["nodes"][-1]
        depth = before["branch_depth"]
        if depth and (node.get("mainline_segment_id") is not None or "mainline_option_index" in node or node["ending_type"] == "main"):
            raise ValueError("支线不能自行改标主线、主结局或重置层级；请回汇到已存在主线")
        if depth == 0 and node["kind"] == "choice" and "mainline_option_index" not in node:
            raise ValueError("主线选择必须标明mainline_option_index，不指定未来节点")
        node.update(branch_depth=depth, return_bias=before["return_bias"],
                    bias_origin_frontier_id=before["bias_origin_frontier_id"])
        children = [f for f in graph["frontiers"] if int(f["frontier_id"].split("-")[-1]) > serial]
        eligible = []
        for child in children:
            child_depth = depth
            if node["kind"] == "choice":
                child_depth = (0 if child["option_index"] == node["mainline_option_index"] else 1) if depth == 0 else depth + 1
            child.update(branch_depth=child_depth, return_bias=before["return_bias"],
                         bias_origin_frontier_id=before["bias_origin_frontier_id"])
            if enabled and child_depth >= 2 and child["return_bias"] is None:
                eligible.append(child)
        if not creating and (not isinstance(draws, list) or len(draws) != len(eligible)):
            raise ValueError("第二层抽签记录缺失或多余")
        for index, child in enumerate(eligible):
            if creating:
                roll = secrets.randbelow(100)
                record = {"frontier_id": child["frontier_id"], "roll": roll,
                          "return_bias": "toward_mainline" if roll < 80 else "free"}
            else:
                record = draws[index]
                _keys(record, {"frontier_id", "roll", "return_bias"}, "脚本抽签记录")
                roll = record["roll"]
                if type(roll) is not int or not 0 <= roll < 100 or record["frontier_id"] != child["frontier_id"]:
                    raise ValueError("抽签数值或路径绑定非法")
                if record["return_bias"] != ("toward_mainline" if roll < 80 else "free"):
                    raise ValueError("抽签结果不符合80%阈值")
            generated.append(record)
            child.update(return_bias=record["return_bias"], bias_origin_frontier_id=child["frontier_id"])
    elif not creating and draws != []:
        raise ValueError("回汇步骤不能附带抽签或重抽")
    return generated


def _load(root: Path, *, check_candidate: bool = True) -> dict[str, Any]:
    state = _read(root / STATE_FILE)
    _keys(state, {"contract_version", "upstream_hashes", "identity", "steps", "state_hash"}, "生长状态")
    if state["contract_version"] not in {LEGACY_VERSION, CONTRACT_VERSION}:
        raise ValueError("生长状态合同版本错误")
    hashes, values, identity = _upstream(root)
    if state["upstream_hashes"] != hashes:
        raise ValueError("冻结输入已改动，与生长状态绑定的哈希不一致")
    if state["identity"] != identity:
        raise ValueError("生长状态项目身份与冻结输入不一致")
    segment_ids, movement_ids = _references(values)
    version = state["contract_version"]
    current = digest({"contract_version": version, "upstream_hashes": hashes, "identity": identity})
    if not isinstance(state["steps"], list):
        raise ValueError("steps必须是不可变追加步骤数组")
    graph = _initial_graph(version)
    enabled = values["user-intent-lock.json"].get("shape_mode") != "exact"
    for index, step in enumerate(state["steps"], 1):
        fields = {"index", "previous_hash", "submission", "nonce", "state_hash"}
        if version == CONTRACT_VERSION:
            fields.add("branch_draws")
        _keys(step, fields, "历史步骤")
        if type(step["index"]) is not int or step["index"] != index or step["previous_hash"] != current:
            raise ValueError("历史步骤索引或前序哈希被改写")
        nonce = step["nonce"]
        if not isinstance(nonce, str) or len(nonce) != 64 or any(char not in "0123456789abcdef" for char in nonce):
            raise ValueError("历史步骤缺少有效脚本nonce")
        expected = digest({key: value for key, value in step.items() if key != "state_hash"})
        if step["state_hash"] != expected:
            raise ValueError("历史步骤内容哈希失效")
        _repair_policy(graph, step["submission"], values, root)
        if version == CONTRACT_VERSION:
            _advance_with_bias(graph, step["submission"], current, segment_ids, movement_ids,
                               step["branch_draws"], enabled)
        else:
            _advance(graph, step["submission"], current, segment_ids, movement_ids)
        current = expected
    if state["state_hash"] != current:
        raise ValueError("生长状态末端哈希失效")
    result = {**state, **graph, "sampling_enabled": version == CONTRACT_VERSION and enabled,
              "status": "IN_PROGRESS" if graph["frontiers"] else "COMPLETE"}
    if check_candidate and (root / CANDIDATE_FILE).exists():
        if graph["frontiers"]:
            raise ValueError("前沿未闭合却已存在候选路线")
        candidate, _ = _project(result)
        if (root / CANDIDATE_FILE).read_bytes() != serialized(candidate):
            raise ValueError("route-candidate.json不是当前历史的逐字确定性投影")
    return result


def load_state(cache_root: Path | str) -> dict[str, Any]:
    """Return a verified replay, including authored lineage on growth nodes."""
    return _load(Path(cache_root))


def _status(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    frontier = deepcopy(state["frontiers"][0]) if state["frontiers"] else None
    if frontier and state["contract_version"] == CONTRACT_VERSION:
        bias = frontier["return_bias"]
        frontier["growth_guidance"] = ("用户锁定完整形状，本轮不抽签，遵守锁定连接。" if not state["sampling_enabled"] else
            "只从当前后果逐步靠近主线；不预写归途或未来汇点，事实与任务成立才回汇。" if bias == "toward_mainline" else
            "保持自由外延，可以继续支出，也可以自然回汇；不因层数增加重抽。" if bias == "free" else
            "按当前事实自然生长；主线分出算第一层，支线再次分岔后各新路径一次抽签。")
        if bias == "toward_mainline":
            frontier["existing_mainline_nodes"] = [{"node_id": n["node_id"], "title": n["title"], "kind": n["kind"]}
                for n in state["nodes"] if n["branch_depth"] == 0]
    return {"contract_version": state["contract_version"], "status": state["status"],
            "state_hash": state["state_hash"], "next_frontier": frontier,
            "node_count": len(state["nodes"]), "frontier_count": len(state["frontiers"]),
            "next_action": "ADVANCE_GROWTH" if frontier else
                ("GROWTH_MATERIALIZED" if (root / CANDIDATE_FILE).exists() else "MATERIALIZE_GROWTH")}


def status(cache_root: Path | str) -> dict[str, Any]:
    root = Path(cache_root)
    return _status(root, load_state(root))


def init(cache_root: Path | str) -> dict[str, Any]:
    root = Path(cache_root)
    with _lock(root):
        if (root / STATE_FILE).exists() or (root / CANDIDATE_FILE).exists():
            raise ValueError("已有生长状态或候选，拒绝覆盖初始化")
        hashes, values, identity = _upstream(root)
        _references(values)
        # Reject malformed slicing before any nodes are accepted.
        story = values["complete-story.json"].get("complete_story")
        if isinstance(story, str):
            from planning_gate import validate_upstream
            errors = []
            validate_upstream(root, errors)
            if errors:
                raise ValueError("生长前修正上游输入（尚未创建节点）：" + "；".join(errors))
        head = {"contract_version": CONTRACT_VERSION, "upstream_hashes": hashes, "identity": identity}
        _atomic(root / STATE_FILE, {**head, "steps": [], "state_hash": digest(head)})
        return status(root)


def append(cache_root: Path | str, submission: Any) -> dict[str, Any]:
    root = Path(cache_root)
    with _lock(root):
        state = _load(root)
        repairing = isinstance(submission, dict) and isinstance(submission.get("action"), dict) and submission["action"].get("type") == "repair"
        if (root / CANDIDATE_FILE).exists() and not repairing:
            raise ValueError("已投影封存，拒绝追加历史")
        _, values, _ = _upstream(root)
        graph = {field: deepcopy(state[field]) for field in ("nodes", "edges", "frontiers", "frontier_serial", "node_serial")}
        _repair_policy(graph, submission, values, root)
        draws = None
        if state["contract_version"] == CONTRACT_VERSION:
            draws = _advance_with_bias(graph, submission, state["state_hash"], *_references(values),
                None, values["user-intent-lock.json"].get("shape_mode") != "exact", creating=True)
        else:
            _advance(graph, submission, state["state_hash"], *_references(values))
        # The next API hash cannot be precomputed before this append returns.
        # This randomness does not stop a same-permission writer rebuilding files.
        step = {"index": len(state["steps"]) + 1, "previous_hash": state["state_hash"],
                "submission": deepcopy(submission), "nonce": os.urandom(32).hex()}
        if draws is not None:
            step["branch_draws"] = draws
        step["state_hash"] = digest(step)
        persisted = {field: state[field] for field in ("contract_version", "upstream_hashes", "identity")}
        persisted.update(steps=state["steps"] + [step], state_hash=step["state_hash"])
        # Recheck source bytes before committing the only permitted append.
        if _upstream(root)[0] != state["upstream_hashes"]:
            raise ValueError("追加期间冻结输入发生变化")
        if repairing:
            archive = root / "repair-history" / str(step["index"])
            archive.mkdir(parents=True, exist_ok=True)
            for name in (CANDIDATE_FILE, "topology-review.json", "emotional-spine.json", "planning-acceptance.json"):
                path = root / name
                if path.exists():
                    _atomic(archive / name, _read(path))
                    path.unlink()
        _atomic(root / STATE_FILE, persisted)
        return status(root)


def _project(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    if state["frontiers"]:
        raise ValueError("全部前沿闭合前不得materialize")
    by_id = {node["node_id"]: node for node in state["nodes"]}
    if not by_id:
        raise ValueError("不能投影空路线")
    rank = {key: index for index, key in enumerate(by_id)}
    outgoing = {key: [] for key in by_id}
    indegree = {key: 0 for key in by_id}
    for edge in state["edges"]:
        outgoing[edge["source_node_id"]].append(edge)
        indegree[edge["target_node_id"]] += 1
    for edges in outgoing.values():
        edges.sort(key=lambda edge: -1 if edge["option_index"] is None else edge["option_index"])
    entries = [key for key, degree in indegree.items() if degree == 0]
    if entries != [next(iter(by_id))]:
        raise ValueError("生长图必须有且只有原始入口")
    # Shortest distance preserves breadth-first preference; Kahn readiness always
    # takes precedence so every merge receives IDs after all direct predecessors.
    depth = {entries[0]: 0}
    queue = list(entries)
    for source in queue:
        for edge in outgoing[source]:
            target = edge["target_node_id"]
            if target not in depth:
                depth[target] = depth[source] + 1
                queue.append(target)
    ready = [(0, rank[entries[0]], entries[0])]
    ordered: list[str] = []
    while ready:
        _, _, source = heapq.heappop(ready)
        ordered.append(source)
        for edge in outgoing[source]:
            target = edge["target_node_id"]
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, (depth[target], rank[target], target))
    if len(ordered) != len(by_id):
        raise ValueError("生长图有循环或不可达节点")
    mapping = {key: f"episode-{index:03d}" for index, key in enumerate(ordered, 1)}
    predecessors: dict[str, list[str]] = {key: [] for key in by_id}
    for source in ordered:
        for edge in outgoing[source]:
            predecessors[edge["target_node_id"]].append(mapping[source])
    nodes = []
    for source in ordered:
        authored = by_id[source]
        successors = [mapping[edge["target_node_id"]] for edge in outgoing[source]]
        choice = authored["kind"] == "choice"
        ending = authored["kind"] == "ending"
        options = [{"选项编号": f"option-{edge['option_index'] + 1:03d}",
                    "选项文字": authored["options"][edge["option_index"]],
                    "目标分集编号": mapping[edge["target_node_id"]]} for edge in outgoing[source]] if choice else []
        nodes.append({"node_id": mapping[source], "node_type": "episode", "分集标题": authored["title"],
            "route_material": deepcopy(authored["route_material"]), "前置节点编号列表": predecessors[source],
            "后续节点编号列表": successors, "是否结局": ending, "ending_type": authored["ending_type"],
            "互动节点": {"是否为分支节点": choice, "是否有选择问题": choice,
                         "选择问题": authored["question"] if choice else "", "选项列表": options,
                         "默认下一分集编号": successors[0] if successors else "无"},
            "node_route_material_hash": ""})
    edges, choices, endings = expected_indexes(nodes)
    route = {"contract_version": ROUTE_VERSION, "capability_id": CAPABILITY_ID, **state["identity"],
             "route_status": "draft", "route_input_hash": digest(state["upstream_hashes"]),
             "route_output_hash": "", "accepted_at": None,
             "nodes": nodes, "edges": edges, "choices": choices, "endings": endings}
    issues = validate_route(route, require_accepted=False)
    if issues:
        raise ValueError("最终投影不满足路线合同：" + "；".join(issues))
    return route, mapping


def projection(cache_root: Path | str) -> dict[str, Any]:
    return _project(load_state(cache_root))[0]


def node_id_map(cache_root: Path | str) -> dict[str, str]:
    return _project(load_state(cache_root))[1]


def materialize(cache_root: Path | str) -> dict[str, Any]:
    root = Path(cache_root)
    with _lock(root):
        state = _load(root)
        candidate, _ = _project(state)
        if not (root / CANDIDATE_FILE).exists():
            _atomic(root / CANDIDATE_FILE, candidate)
        return status(root)


def verify_root(cache_root: Path | str) -> list[str]:
    """Require a complete valid chain and an exact existing candidate projection."""
    root = Path(cache_root)
    try:
        state = _load(root)
        if state["frontiers"]:
            return ["生长前沿尚未全部关闭"]
        if not (root / CANDIDATE_FILE).is_file():
            return ["缺少脚本投影的route-candidate.json"]
        return []
    except (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "append", "materialize"):
        command = commands.add_parser(name)
        command.add_argument("cache_root", type=Path)
        if name == "append":
            command.add_argument("submission", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "append":
            result = append(args.cache_root, _read(args.submission))
        else:
            result = {"init": init, "status": status, "materialize": materialize}[args.command](args.cache_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError) as error:
        print(f"FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
