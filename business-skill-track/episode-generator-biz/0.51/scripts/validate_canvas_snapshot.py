#!/usr/bin/env python3
"""Resolve current display positions once, then lock stable route node references."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


VERSION = "nextplay.canvas-current-snapshot.v2"
RECEIPT_VERSION = "nextplay.canvas-scan-receipt.v2"
OPERATIONS = {"add", "generate", "update", "delete", "move", "reconnect"}
ROOT_FIELDS = {
    "contract_version", "scope", "project_revision", "user_request_sha256",
    "node_count", "operation", "selections", "nodes",
}
NODE_FIELDS = {
    "node_ref", "display_number", "display_id", "display_name",
    "predecessors", "successors", "choices",
}
CHOICE_FIELDS = {"text", "target_ref"}
SELECTION_FIELDS = {"selector", "purpose", "node_ref"}
POSITION_SELECTOR = re.compile(r"^第\s*(\d+)\s*(?:集|个?节点)$")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def selector_number(selector: str) -> int | None:
    value = selector.strip()
    if value.isdigit():
        return int(value)
    match = POSITION_SELECTOR.fullmatch(value)
    return int(match.group(1)) if match else None


def selector_matches(node: dict[str, Any], selector: str) -> bool:
    number = selector_number(selector)
    if number is not None:
        return node["display_number"] == number
    value = selector.strip()
    return value in {node["display_id"], node["display_name"]}


def validate(data: Any, request_bytes: bytes) -> tuple[list[str], dict[str, Any] | None]:
    issues: list[str] = []
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS:
        return ["当前画布快照根字段错误"], None
    if data.get("contract_version") != VERSION or data.get("scope") != "full-graph":
        issues.append("当前画布快照合同或扫描范围错误")
    revision = data.get("project_revision")
    if not isinstance(revision, str) or not revision.strip():
        issues.append("当前画布快照缺少平台project_revision")
    request_sha = sha256_bytes(request_bytes)
    if data.get("user_request_sha256") != request_sha:
        issues.append("当前画布快照未绑定本轮用户请求")
    operation = data.get("operation")
    if operation not in OPERATIONS:
        issues.append("当前画布操作类型错误")

    nodes_value = data.get("nodes")
    if not isinstance(nodes_value, list) or not nodes_value:
        return [*issues, "当前画布快照没有节点"], None
    if data.get("node_count") != len(nodes_value):
        issues.append("当前画布节点总数与扫描数组不一致")

    by_ref: dict[str, dict[str, Any]] = {}
    display_numbers: dict[int, str] = {}
    display_ids: dict[str, str] = {}
    for index, node in enumerate(nodes_value):
        if not isinstance(node, dict) or set(node) != NODE_FIELDS:
            issues.append(f"节点字段错误：index={index}")
            continue
        ref = node.get("node_ref")
        number = node.get("display_number")
        display_id = node.get("display_id")
        display_name = node.get("display_name")
        if not isinstance(ref, str) or not ref or ref in by_ref:
            issues.append(f"节点node_ref为空或重复：index={index}")
            continue
        by_ref[ref] = node
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            issues.append(f"节点display_number必须是正整数：{ref}")
        elif number in display_numbers:
            issues.append(f"节点display_number重复：{number}")
        else:
            display_numbers[number] = ref
        if not isinstance(display_id, str) or not display_id.strip():
            issues.append(f"节点display_id为空：{ref}")
        elif display_id in display_ids:
            issues.append(f"节点display_id重复：{display_id}")
        else:
            display_ids[display_id] = ref
        if not isinstance(display_name, str) or not display_name.strip():
            issues.append(f"节点display_name为空：{ref}")
        for field in ("predecessors", "successors"):
            values = node.get(field)
            if not string_list(values) and values != []:
                issues.append(f"节点{field}必须是不透明node_ref数组：{ref}")
            elif isinstance(values, list) and len(values) != len(set(values)):
                issues.append(f"节点{field}存在重复：{ref}")
        choices = node.get("choices")
        if not isinstance(choices, list):
            issues.append(f"节点choices必须是数组：{ref}")
        else:
            targets: list[str] = []
            for choice in choices:
                if not isinstance(choice, dict) or set(choice) != CHOICE_FIELDS:
                    issues.append(f"选项字段错误：{ref}")
                    continue
                if not isinstance(choice.get("text"), str) or not choice["text"].strip():
                    issues.append(f"选项文字为空：{ref}")
                target = choice.get("target_ref")
                if not isinstance(target, str) or not target:
                    issues.append(f"选项目标为空：{ref}")
                else:
                    targets.append(target)
            if targets and set(targets) != set(node.get("successors") or []):
                issues.append(f"选项目标与出边不一致：{ref}")

    if set(display_numbers) != set(range(1, len(nodes_value) + 1)):
        issues.append("最新route的display_number必须从1连续排列到节点总数")

    refs = set(by_ref)
    edge_count = 0
    for ref, node in by_ref.items():
        predecessors = node.get("predecessors") or []
        successors = node.get("successors") or []
        edge_count += len(successors)
        for source in predecessors:
            if source not in refs:
                issues.append(f"入边引用不存在：{source}->{ref}")
            elif ref not in (by_ref[source].get("successors") or []):
                issues.append(f"入边与出边不对称：{source}->{ref}")
        for target in successors:
            if target not in refs:
                issues.append(f"出边引用不存在：{ref}->{target}")
            elif ref not in (by_ref[target].get("predecessors") or []):
                issues.append(f"出边与入边不对称：{ref}->{target}")

    selections = data.get("selections")
    if not isinstance(selections, list):
        issues.append("selections必须是数组")
        selections = []
    resolved: list[dict[str, Any]] = []
    for index, selection in enumerate(selections):
        if not isinstance(selection, dict) or set(selection) != SELECTION_FIELDS:
            issues.append(f"位置解析字段错误：index={index}")
            continue
        selector = selection.get("selector")
        purpose = selection.get("purpose")
        ref = selection.get("node_ref")
        if not isinstance(selector, str) or not selector.strip():
            issues.append(f"位置解析缺少用户定位词：index={index}")
            continue
        if purpose not in {"target", "anchor"}:
            issues.append(f"位置解析purpose错误：index={index}")
            continue
        if not isinstance(ref, str) or ref not in refs:
            issues.append(f"位置解析node_ref不在当前route：index={index}")
            continue
        matches = [candidate for candidate, node in by_ref.items() if selector_matches(node, selector)]
        if matches != [ref]:
            issues.append(f"定位词没有通过最新display字段唯一锁定node_ref：{selector}")
            continue
        node = by_ref[ref]
        resolved.append({
            "selector": selector,
            "purpose": purpose,
            "node_ref": ref,
            "display_number": node["display_number"],
            "display_id": node["display_id"],
            "display_name": node["display_name"],
        })

    target_refs = [item["node_ref"] for item in resolved if item["purpose"] == "target"]
    anchor_refs = [item["node_ref"] for item in resolved if item["purpose"] == "anchor"]
    if len(target_refs) != len(set(target_refs)) or len(anchor_refs) != len(set(anchor_refs)):
        issues.append("同一用途不得重复锁定node_ref")
    if operation in {"add", "generate", "update", "move"} and len(target_refs) != 1:
        issues.append("新增、生成、修改或移动必须唯一锁定一个目标node_ref")
    if operation == "delete" and not anchor_refs:
        issues.append("删除后理顺必须锁定当前route中的接缝锚点")
    if operation == "move" and not anchor_refs:
        issues.append("移动必须锁定当前route中的落点锚点")
    if operation == "reconnect" and len(anchor_refs) < 2:
        issues.append("重连必须锁定至少两个当前route锚点")
    if issues:
        return list(dict.fromkeys(issues)), None

    locked_ref = target_refs[0] if target_refs else None
    target_context = None
    if locked_ref:
        node = by_ref[locked_ref]
        target_context = {
            "node_ref": locked_ref,
            "predecessors": node["predecessors"],
            "successors": node["successors"],
        }
    receipt = {
        "contract_version": RECEIPT_VERSION,
        "status": "PASS",
        "project_revision": revision,
        "user_request_sha256": request_sha,
        "snapshot_sha256": sha256_bytes(canonical(data)),
        "node_count": len(nodes_value),
        "edge_count": edge_count,
        "operation": operation,
        "locked_node_ref": locked_ref,
        "locked_anchor_node_refs": anchor_refs,
        "resolution_audit": resolved,
        "target_context": target_context,
    }
    return [], receipt


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("user_request", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.snapshot.read_text(encoding="utf-8"))
        issues, receipt = validate(data, args.user_request.read_bytes())
        if issues:
            print("FAIL")
            for issue in issues:
                print(f"- {issue}")
            return 1
        atomic_write(args.receipt, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: latest display resolved and stable node_ref locked; revision={receipt['project_revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
