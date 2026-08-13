#!/usr/bin/env python3
"""Validate a fresh full-canvas scan before any user-directed local node edit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


VERSION = "nextplay.canvas-current-snapshot.v1"
RECEIPT_VERSION = "nextplay.canvas-scan-receipt.v1"
OPERATIONS = {"add", "generate", "update", "delete", "reconnect"}
ROOT_FIELDS = {
    "contract_version", "scope", "project_revision", "user_request_sha256",
    "node_count", "operation", "target_selector", "target_node_refs",
    "anchor_node_refs", "nodes",
}
NODE_FIELDS = {"node_ref", "display_id", "title", "predecessors", "successors", "choices"}
CHOICE_FIELDS = {"text", "target_ref"}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


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
    selector = data.get("target_selector")
    if not isinstance(selector, str) or not selector.strip():
        issues.append("缺少用户目标定位词")

    nodes_value = data.get("nodes")
    if not isinstance(nodes_value, list) or not nodes_value:
        return [*issues, "当前画布快照没有节点"], None
    if data.get("node_count") != len(nodes_value):
        issues.append("当前画布节点总数与扫描数组不一致")

    by_ref: dict[str, dict[str, Any]] = {}
    display_ids: dict[str, str] = {}
    for index, node in enumerate(nodes_value):
        if not isinstance(node, dict) or set(node) != NODE_FIELDS:
            issues.append(f"节点字段错误：index={index}")
            continue
        ref = node.get("node_ref")
        display_id = node.get("display_id")
        title = node.get("title")
        if not isinstance(ref, str) or not ref or ref in by_ref:
            issues.append(f"节点node_ref为空或重复：index={index}")
            continue
        by_ref[ref] = node
        if not isinstance(display_id, str) or not display_id:
            issues.append(f"节点display_id为空：{ref}")
        elif display_id in display_ids:
            issues.append(f"节点display_id重复：{display_id}")
        else:
            display_ids[display_id] = ref
        if not isinstance(title, str) or not title.strip():
            issues.append(f"节点标题为空：{ref}")
        for field in ("predecessors", "successors"):
            values = node.get(field)
            if not string_list(values) and values != []:
                issues.append(f"节点{field}必须是不透明引用数组：{ref}")
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

    targets = data.get("target_node_refs")
    anchors = data.get("anchor_node_refs")
    if not string_list(targets) and targets != []:
        issues.append("target_node_refs必须是节点引用数组")
        targets = []
    if not string_list(anchors) and anchors != []:
        issues.append("anchor_node_refs必须是节点引用数组")
        anchors = []
    for ref in [*(targets or []), *(anchors or [])]:
        if ref not in refs:
            issues.append(f"目标或锚点不在当前全图快照：{ref}")
    if operation in {"add", "generate", "update"}:
        if not isinstance(targets, list) or len(targets) != 1:
            issues.append("新增、生成或修改必须唯一解析一个当前目标节点")
        elif isinstance(selector, str):
            node = by_ref.get(targets[0])
            if node and selector.strip() not in {targets[0], node["display_id"], node["title"]}:
                issues.append("用户目标定位词与当前快照的唯一目标不一致")
    if operation == "delete" and not anchors:
        issues.append("删除后理顺前后剧情必须指定当前图的接缝锚点")
    if operation == "reconnect" and (not isinstance(anchors, list) or len(anchors) < 2):
        issues.append("重连操作必须至少定位两个当前图锚点")
    if issues:
        return list(dict.fromkeys(issues)), None

    target_context = []
    for ref in targets or []:
        node = by_ref[ref]
        target_context.append({
            "node_ref": ref,
            "display_id": node["display_id"],
            "title": node["title"],
            "predecessors": node["predecessors"],
            "successors": node["successors"],
        })
    receipt = {
        "contract_version": RECEIPT_VERSION,
        "status": "PASS",
        "project_revision": revision,
        "user_request_sha256": request_sha,
        "snapshot_sha256": sha256_bytes(canonical(data)),
        "node_count": len(nodes_value),
        "edge_count": edge_count,
        "operation": operation,
        "target_selector": selector,
        "target_context": target_context,
        "anchor_node_refs": anchors,
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
        request_bytes = args.user_request.read_bytes()
        issues, receipt = validate(data, request_bytes)
        if issues:
            print("FAIL")
            for issue in issues:
                print(f"- {issue}")
            return 1
        atomic_write(args.receipt, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: full canvas scanned; revision={receipt['project_revision']}; nodes={receipt['node_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
