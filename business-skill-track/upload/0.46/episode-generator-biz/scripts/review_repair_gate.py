#!/usr/bin/env python3
"""Merge review findings and prove that an Enhancer repair stayed local."""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from episode_artifact import section, subsection
from validate_screenwriter_draft import validate as validate_script_shape


FINDINGS_VERSION = "nextplay.episode-review-findings.v1"
MERGED_VERSION = "nextplay.episode-merged-findings.v1"
REPAIR_RECEIPT_VERSION = "nextplay.episode-local-repair.v1"
SOURCES = {"dramatization", "cold-read"}
ISSUE_FIELDS = {"issue_id", "category", "start_line", "end_line", "anchor", "reason"}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


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


def enhanced_path(cache_root: Path, episode_id: str) -> Path:
    return cache_root / "enhanced-screenplays" / f"{episode_id}.md"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON必须是对象：{path}")
    return value


def validate_findings(data: dict[str, Any], episode_id: str, script: str) -> list[str]:
    errors: list[str] = []
    expected = {"contract_version", "episode_id", "source", "script_sha256", "status", "rewrite_required", "issues"}
    if set(data) != expected:
        return ["复检问题单根字段错误"]
    if data.get("contract_version") != FINDINGS_VERSION or data.get("episode_id") != episode_id:
        errors.append("复检问题单合同或编号错误")
    if data.get("source") not in SOURCES:
        errors.append("复检问题单来源错误")
    if data.get("script_sha256") != sha_text(script):
        errors.append("复检问题单未绑定当前增强稿")
    issues = data.get("issues")
    if not isinstance(issues, list):
        return [*errors, "复检问题必须是数组"]
    if data.get("status") not in {"PASS", "FAIL"}:
        errors.append("复检问题单状态错误")
    if data.get("status") == "PASS" and issues:
        errors.append("PASS问题单不得包含问题")
    if data.get("status") == "FAIL" and not issues:
        errors.append("FAIL问题单必须定位问题")
    if not isinstance(data.get("rewrite_required"), bool):
        errors.append("rewrite_required必须是布尔值")
    lines = script.splitlines()
    seen: set[str] = set()
    for index, issue in enumerate(issues, 1):
        if not isinstance(issue, dict) or set(issue) != ISSUE_FIELDS:
            errors.append(f"问题字段错误：{index}")
            continue
        issue_id = str(issue.get("issue_id") or "").strip()
        category = str(issue.get("category") or "").strip()
        anchor = str(issue.get("anchor") or "").strip()
        reason = str(issue.get("reason") or "").strip()
        start = issue.get("start_line")
        end = issue.get("end_line")
        if not issue_id or issue_id in seen:
            errors.append(f"问题编号为空或重复：{index}")
        seen.add(issue_id)
        if len(category) < 2 or len(reason) < 8 or len(anchor) < 2:
            errors.append(f"问题定位或原因过短：{issue_id}")
        if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start or end > len(lines):
            errors.append(f"问题行号非法：{issue_id}")
            continue
        if anchor not in "\n".join(lines[start - 1:end]):
            errors.append(f"问题原文锚点不在授权行：{issue_id}")
        if any(key in issue for key in ("replacement", "rewrite", "suggested_text")):
            errors.append(f"复检者不得提供替换正文：{issue_id}")
    return list(dict.fromkeys(errors))


def merged_ranges(issues: list[dict[str, Any]]) -> list[list[int]]:
    ranges = sorted((int(item["start_line"]), int(item["end_line"])) for item in issues)
    result: list[list[int]] = []
    for start, end in ranges:
        if result and start <= result[-1][1] + 1:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def merge(cache_root: Path, episode_id: str, finding_paths: list[Path]) -> dict[str, Any]:
    script = enhanced_path(cache_root, episode_id).read_text(encoding="utf-8").strip()
    if not script:
        raise ValueError("缺少当前增强稿")
    findings = [read_json(path) for path in finding_paths]
    if {item.get("source") for item in findings} != SOURCES:
        raise ValueError("必须同时提供场面复检与独立冷读问题单")
    errors: list[str] = []
    for item in findings:
        errors.extend(validate_findings(item, episode_id, script))
    if errors:
        raise ValueError("；".join(dict.fromkeys(errors)))
    issues: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in findings:
        for issue in item["issues"]:
            key = (issue["category"], issue["start_line"], issue["end_line"], issue["anchor"], issue["reason"])
            if key not in seen:
                copied = dict(issue)
                copied["source"] = item["source"]
                issues.append(copied)
                seen.add(key)
    ranges = merged_ranges(issues)
    lines = script.splitlines()
    content_lines = {index for index, line in enumerate(lines, 1) if line.strip() and not re.fullmatch(r"【[^】]+】", line.strip())}
    authorized = {index for start, end in ranges for index in range(start, end + 1)}
    rewrite_required = any(bool(item["rewrite_required"]) for item in findings) or bool(content_lines and content_lines <= authorized)
    return {
        "contract_version": MERGED_VERSION,
        "episode_id": episode_id,
        "script_sha256": sha_text(script),
        "finding_sha256": [sha_bytes(canonical(item)) for item in findings],
        "rewrite_required": rewrite_required,
        "authorized_ranges": ranges,
        "issues": issues,
    }


def build_input(cache_root: Path, episode_id: str, merged_path: Path, reference_path: Path) -> str:
    script = enhanced_path(cache_root, episode_id).read_text(encoding="utf-8").strip()
    merged = read_json(merged_path)
    if merged.get("contract_version") != MERGED_VERSION or merged.get("episode_id") != episode_id:
        raise ValueError("合并问题单合同或编号错误")
    if merged.get("script_sha256") != sha_text(script):
        raise ValueError("合并问题单未绑定当前增强稿")
    if merged.get("rewrite_required"):
        raise ValueError("问题覆盖整集或材料层，禁止局部修复；必须重新经过Screenwriter与完整Enhancer")
    if not merged.get("issues") or not merged.get("authorized_ranges"):
        raise ValueError("没有需要局部修复的问题")
    material = read_json(cache_root / "episode-story-materials" / f"{episode_id}.json")
    boundary = str(material.get("stop_boundary") or "").strip()
    reference = reference_path.read_text(encoding="utf-8").strip()
    if not reference or not boundary:
        raise ValueError("局部修复缺少reference或停止边界")
    return (
        "REPAIR_INPUT_VERSION=nextplay.episode-local-repair-input.v1\n"
        f"EPISODE_ID={episode_id}\n"
        f"BASELINE_SHA256={sha_text(script)}\n\n"
        "# 停止边界\n" + boundary + "\n\n"
        "# Enhancer局部修复Reference\n" + reference + "\n\n"
        "# 合并问题单\n" + json.dumps(merged, ensure_ascii=False, indent=2) + "\n\n"
        "# 当前增强稿\n" + script + "\n"
    )


def opcode_allowed(tag: str, i1: int, i2: int, ranges: list[list[int]]) -> bool:
    intervals = [(start - 1, end) for start, end in ranges]
    if tag == "insert":
        return any(start <= i1 <= end for start, end in intervals)
    return any(start <= i1 and i2 <= end for start, end in intervals)


def verify_repair(cache_root: Path, episode_id: str, baseline_path: Path, merged_path: Path) -> dict[str, Any]:
    baseline = baseline_path.read_text(encoding="utf-8").strip()
    repaired = enhanced_path(cache_root, episode_id).read_text(encoding="utf-8").strip()
    merged = read_json(merged_path)
    if merged.get("contract_version") != MERGED_VERSION or merged.get("episode_id") != episode_id:
        raise ValueError("合并问题单合同或编号错误")
    if merged.get("script_sha256") != sha_text(baseline):
        raise ValueError("合并问题单未绑定修复前增强稿")
    if merged.get("rewrite_required"):
        raise ValueError("整集重写不得伪装为局部修复")
    if baseline == repaired:
        raise ValueError("局部修复没有改变任何授权内容")
    baseline_lines = baseline.splitlines()
    repaired_lines = repaired.splitlines()
    changes: list[dict[str, Any]] = []
    unchanged_content = False
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=baseline_lines, b=repaired_lines, autojunk=False).get_opcodes():
        if tag == "equal":
            if any(line.strip() for line in baseline_lines[i1:i2]):
                unchanged_content = True
            continue
        if not opcode_allowed(tag, i1, i2, merged.get("authorized_ranges") or []):
            raise ValueError(f"局部修复改动了未授权行：{tag}/{i1 + 1}-{i2}")
        changes.append({"tag": tag, "before": [i1 + 1, i2], "after": [j1 + 1, j2]})
    if not changes or not unchanged_content:
        raise ValueError("局部修复覆盖整集；必须重新经过Screenwriter与完整Enhancer")
    shape_errors = validate_script_shape(repaired)
    if shape_errors:
        raise ValueError("局部修复破坏剧本最低形态：" + "；".join(shape_errors))
    episode_path = cache_root / "episodes" / f"{episode_id}.md"
    artifact = episode_path.read_text(encoding="utf-8").strip()
    formal = subsection(section(artifact, "分集剧本"), "完整剧本")
    if formal != repaired:
        raise ValueError("正式正文不是局部修复后增强稿的逐字副本")
    return {
        "contract_version": REPAIR_RECEIPT_VERSION,
        "episode_id": episode_id,
        "baseline_sha256": sha_text(baseline),
        "merged_findings_sha256": sha_bytes(canonical(merged)),
        "repaired_sha256": sha_text(repaired),
        "formal_episode_sha256": sha_bytes(episode_path.read_bytes()),
        "authorized_ranges": merged["authorized_ranges"],
        "changes": changes,
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    merge_parser = sub.add_parser("merge")
    merge_parser.add_argument("cache_root", type=Path)
    merge_parser.add_argument("episode_id")
    merge_parser.add_argument("dramatization_findings", type=Path)
    merge_parser.add_argument("quality_findings", type=Path)
    merge_parser.add_argument("--output", type=Path, required=True)
    input_parser = sub.add_parser("input")
    input_parser.add_argument("cache_root", type=Path)
    input_parser.add_argument("episode_id")
    input_parser.add_argument("merged", type=Path)
    input_parser.add_argument("--reference", type=Path, required=True)
    input_parser.add_argument("--output", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("cache_root", type=Path)
    verify_parser.add_argument("episode_id")
    verify_parser.add_argument("baseline", type=Path)
    verify_parser.add_argument("merged", type=Path)
    verify_parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "merge":
            value = merge(args.cache_root, args.episode_id, [args.dramatization_findings, args.quality_findings])
            atomic_write(args.output, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        elif args.command == "input":
            atomic_write(args.output, build_input(args.cache_root, args.episode_id, args.merged, args.reference))
        else:
            receipt = verify_repair(args.cache_root, args.episode_id, args.baseline, args.merged)
            atomic_write(args.receipt, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: {args.command} {args.episode_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
