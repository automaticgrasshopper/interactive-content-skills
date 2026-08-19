#!/usr/bin/env python3
"""Safely repair bookkeeping around an already valid mainline route.

This script never adds topology edges or changes story facts.  When continuity
itself is broken it emits a small regeneration scope instead of guessing.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from validate_mainline_projection import PATH_VERSION, full_issues, topology_issues
from validate_route_duration import graph_paths
from validate_topology import parse


REPORT_VERSION = "nextplay.mainline-projection-repair.v1"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def segments(cache_root: Path) -> list[dict[str, str]]:
    value = load(cache_root / "mainline-decomposition.json")
    result = value.get("segments")
    if not isinstance(result, list) or not result:
        raise ValueError("主线分解缺少segments")
    return [
        {
            "segment_id": str(item.get("segment_id") or ""),
            "source_text": str(item.get("source_text") or ""),
        }
        for item in result
        if isinstance(item, dict)
    ]


def mapping_from_current(cache_root: Path, source: list[dict[str, str]]) -> list[dict[str, str]] | None:
    value = load(cache_root / "mainline-path.json")
    current = value.get("path")
    if not isinstance(current, list):
        return None
    by_segment: dict[str, str] = {}
    for item in current:
        if not isinstance(item, dict):
            return None
        segment_id = str(item.get("segment_id") or "")
        episode_id = str(item.get("episode_id") or "")
        if segment_id in by_segment or not episode_id:
            return None
        by_segment[segment_id] = episode_id
    ordered = [
        {"segment_id": item["segment_id"], "episode_id": by_segment.get(item["segment_id"], "")}
        for item in source
    ]
    if any(not item["episode_id"] for item in ordered):
        return None
    if len({item["episode_id"] for item in ordered}) != len(ordered):
        return None
    return ordered


def mapping_from_synopses(cache_root: Path, source: list[dict[str, str]]) -> list[dict[str, str]] | None:
    folder = cache_root / "episode-synopses"
    if not folder.is_dir():
        return None
    by_text: dict[str, list[str]] = {}
    for path in sorted(folder.glob("episode-*.json")):
        value = load(path)
        by_text.setdefault(str(value.get("synopsis") or ""), []).append(path.stem)
    result: list[dict[str, str]] = []
    for item in source:
        matches = by_text.get(item["source_text"], [])
        if len(matches) != 1:
            return None
        result.append({"segment_id": item["segment_id"], "episode_id": matches[0]})
    if len({item["episode_id"] for item in result}) != len(result):
        return None
    return result


def valid_route(cache_root: Path, mapping: list[dict[str, str]]) -> tuple[bool, list[str]]:
    nodes = parse(cache_root / "topology.md")
    episode_ids = [item["episode_id"] for item in mapping]
    reasons: list[str] = []
    if not episode_ids or episode_ids[0] != "episode-001":
        reasons.append("主线路径没有从唯一入口开始")
    missing = [episode_id for episode_id in episode_ids if episode_id not in nodes]
    if missing:
        reasons.append(f"主线路径含不存在节点：{missing}")
        return False, reasons
    for source, target in zip(episode_ids, episode_ids[1:]):
        if target not in nodes[source]["successors"]:
            reasons.append(f"主线节点未直接连接下一主线节点：{source}->{target}")
    if episode_ids:
        final = nodes[episode_ids[-1]]
        if final["successors"]:
            reasons.append("主线路径没有在结局结束")
        if "主结局" not in str(final["interaction"]):
            reasons.append("主线路径没有到达冻结完整故事的主结局")
    return not reasons, reasons


def recompute_duration(cache_root: Path, episode_ids: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
    path = cache_root / "route-duration.json"
    value = load(path)
    nodes = parse(cache_root / "topology.md")
    minutes = value.get("node_minutes")
    if not isinstance(minutes, dict) or set(minutes) != set(nodes):
        return None, ["route-duration/node_minutes未覆盖当前拓扑，不能安全自动修复"]
    paths = graph_paths(nodes)
    if episode_ids not in paths:
        return None, ["当前映射不是实际入口到结局路线，不能安全自动修复"]
    value["mainline_path"] = episode_ids
    value["paths"] = [
        {
            "ending_id": node_ids[-1],
            "node_ids": node_ids,
            "total_minutes": round(sum(float(minutes[node_id]) for node_id in node_ids), 3),
        }
        for node_ids in paths
    ]
    return value, []


def repair(cache_root: Path, apply: bool) -> tuple[dict[str, Any], int]:
    source = segments(cache_root)
    candidates = [
        ("current", mapping_from_current(cache_root, source)),
        ("synopsis", mapping_from_synopses(cache_root, source)),
    ]
    chosen: list[dict[str, str]] | None = None
    chosen_source = ""
    rejected: dict[str, list[str]] = {}
    for name, candidate in candidates:
        if candidate is None:
            rejected[name] = ["无法形成覆盖全部切片的一一映射"]
            continue
        ok, reasons = valid_route(cache_root, candidate)
        if ok:
            chosen = candidate
            chosen_source = name
            break
        rejected[name] = reasons

    report: dict[str, Any] = {
        "contract_version": REPORT_VERSION,
        "status": "REPROJECT_REQUIRED" if chosen is None else "REPAIRABLE",
        "mapping_source": chosen_source or None,
        "changes": [],
        "rejected_candidates": rejected,
        "regenerate_only": [],
    }
    if chosen is None:
        report["regenerate_only"] = [
            "topology.md",
            "mainline-path.json",
            "route-duration.json",
        ]
        report["reason"] = "连续性本身不成立；不得自动添加边或改写故事"
        return report, 2

    episode_ids = [item["episode_id"] for item in chosen]
    duration, duration_errors = recompute_duration(cache_root, episode_ids)
    if duration_errors:
        report["status"] = "REPROJECT_REQUIRED"
        report["regenerate_only"] = ["route-duration.json"]
        report["reason"] = "；".join(duration_errors)
        return report, 2

    new_path = {"contract_version": PATH_VERSION, "path": chosen}
    old_path = load(cache_root / "mainline-path.json")
    if old_path != new_path:
        report["changes"].append("mainline-path.json")
        report["status"] = "REPROJECT_REQUIRED"
        report["regenerate_only"] = [
            "mainline-path.json", "mainline-projection-review.json",
            "route-duration.json", "受影响的episode-synopses/*.json",
        ]
        report["reason"] = "候选路径改变了事件归属；缺少绑定候选路径的独立事件归属复检，自动修复不得覆盖梗概"
        return report, 2
    if load(cache_root / "route-duration.json") != duration:
        report["changes"].append("route-duration.json")

    synopsis_changes: list[tuple[Path, dict[str, Any]]] = []
    folder = cache_root / "episode-synopses"
    if folder.is_dir():
        source_by_id = {item["segment_id"]: item["source_text"] for item in source}
        for item in chosen:
            path = folder / f"{item['episode_id']}.json"
            if not path.is_file():
                continue
            value = load(path)
            expected = source_by_id[item["segment_id"]]
            if value.get("synopsis") != expected:
                value["synopsis"] = expected
                synopsis_changes.append((path, value))
                report["changes"].append(f"episode-synopses/{path.name}")

    report["status"] = "PASS" if not report["changes"] else "REPAIRED"
    if apply:
        if (cache_root / "planning-acceptance.json").exists():
            raise ValueError("阶段二已经冻结；不得原地修复，必须开始新的阶段二运行")
        semantic_issues = [
            issue for issue in topology_issues(cache_root)
            if issue != "主线路径映射与route-duration/mainline_path不一致"
        ]
        if semantic_issues:
            raise ValueError("主线事件归属尚未通过，不得自动覆盖梗概：" + "；".join(semantic_issues))
        atomic_write(cache_root / "mainline-path.json", new_path)
        assert duration is not None
        atomic_write(cache_root / "route-duration.json", duration)
        for path, value in synopsis_changes:
            atomic_write(path, value)
        remaining = full_issues(cache_root) if folder.is_dir() else topology_issues(cache_root)
        if remaining:
            report["status"] = "REPROJECT_REQUIRED"
            report["reason"] = "；".join(remaining)
            return report, 2
    return report, 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report, code = repair(args.cache_root, args.apply)
        if args.report:
            atomic_write(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
