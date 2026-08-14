#!/usr/bin/env python3
"""Verify verbatim mainline decomposition and its one-to-one topology projection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from validate_topology import parse

DECOMPOSITION_VERSION = "nextplay.mainline-decomposition.v1"
PATH_VERSION = "nextplay.mainline-path.v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def decomposition_issues(root: Path) -> tuple[list[str], dict, dict]:
    issues = []
    mainline = load(root / "mainline-story.json")
    decomposition = load(root / "mainline-decomposition.json")
    if decomposition.get("contract_version") != DECOMPOSITION_VERSION:
        issues.append("主线分解合同错误")
    if decomposition.get("mainline_sha256") != sha(canonical(mainline)):
        issues.append("主线分解未绑定当前冻结主线")
    segments = decomposition.get("segments")
    if not isinstance(segments, list) or not segments:
        issues.append("主线分解缺少segments")
        return issues, mainline, decomposition
    story = str(mainline.get("complete_story") or "")
    cursor = 0
    ids = set()
    for index, item in enumerate(segments, 1):
        if not isinstance(item, dict) or set(item) != {"segment_id", "title", "source_text"}:
            issues.append(f"主线切片字段错误：{index}")
            continue
        segment_id = str(item.get("segment_id") or "")
        source = str(item.get("source_text") or "")
        if segment_id in ids or not segment_id.startswith("mainline-"):
            issues.append(f"主线切片编号非法或重复：{segment_id}")
        ids.add(segment_id)
        found = story.find(source, cursor)
        if not source.strip() or found < 0:
            issues.append(f"主线切片不是冻结故事的连续逐字原文：{segment_id}")
            continue
        if story[cursor:found].strip():
            issues.append(f"主线切片之间遗漏原文：{segment_id}")
        cursor = found + len(source)
    if story[cursor:].strip():
        issues.append("主线分解末尾遗漏冻结故事原文")
    return list(dict.fromkeys(issues)), mainline, decomposition


def full_issues(root: Path) -> list[str]:
    issues, mainline, decomposition = decomposition_issues(root)
    path_data = load(root / "mainline-path.json")
    if path_data.get("contract_version") != PATH_VERSION or not isinstance(path_data.get("path"), list):
        return [*issues, "主线路径映射合同错误"]
    mappings = path_data["path"]
    segment_ids = [str(item.get("segment_id")) for item in decomposition.get("segments", [])]
    mapped_segments = [str(item.get("segment_id")) for item in mappings]
    episodes = [str(item.get("episode_id")) for item in mappings]
    if mapped_segments != segment_ids or len(set(episodes)) != len(episodes):
        issues.append("主线路径必须按顺序一一映射全部主线切片")
    duration = load(root / "route-duration.json")
    if episodes != duration.get("mainline_path"):
        issues.append("主线路径映射与route-duration/mainline_path不一致")
    nodes = parse(root / "topology.md")
    source_by_id = {item["segment_id"]: item["source_text"] for item in decomposition.get("segments", [])}
    for index, item in enumerate(mappings):
        episode_id = str(item.get("episode_id"))
        if episode_id not in nodes:
            issues.append(f"主线映射节点不存在：{episode_id}")
            continue
        synopsis_path = root / "episode-synopses" / f"{episode_id}.json"
        if not synopsis_path.is_file():
            issues.append(f"缺少主线分集梗概：{episode_id}")
        elif load(synopsis_path).get("synopsis") != source_by_id.get(str(item.get("segment_id"))):
            issues.append(f"主线分集梗概未逐字使用冻结故事切片：{episode_id}")
        if index + 1 < len(mappings):
            next_id = str(mappings[index + 1].get("episode_id"))
            successors = set(nodes[episode_id]["successors"])
            if next_id not in successors:
                issues.append(f"主线节点未直接连接下一主线节点：{episode_id}->{next_id}")
        elif str(nodes[episode_id]["title"]).strip() != str(mainline.get("expected_ending_title") or "").strip():
            issues.append("主线路径末节点不是冻结期待结局")
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--decomposition-only", action="store_true")
    args = parser.parse_args()
    try:
        issues = decomposition_issues(args.cache_root)[0] if args.decomposition_only else full_issues(args.cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: frozen mainline is verbatim and mapped one-to-one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
