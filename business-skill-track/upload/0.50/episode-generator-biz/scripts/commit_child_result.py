#!/usr/bin/env python3
"""Validate an isolated child result and stage or commit it deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from action_contracts import CHILD_ACTIONS
from dramatization_gate import seal as seal_dramatization
from episode_quality_gate import seal as seal_cold_read
from review_repair_gate import (
    FINDINGS_VERSION,
    atomic_write as write_repair_receipt,
    validate_findings,
    verify_repair,
)
from run_state import complete, fail, load


VERSION = "nextplay.episode-child-result.v1"
FIELDS = {
    "contract_version", "action", "episode_id", "input_sha256",
    "status", "content", "findings",
}


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate(value: Any, episode_id: str, action: str, input_sha256: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("子Agent返回根字段错误")
    if value.get("contract_version") != VERSION:
        raise ValueError("子Agent返回合同版本错误")
    if action not in CHILD_ACTIONS or value.get("action") != action:
        raise ValueError("子Agent返回动作错误")
    if value.get("episode_id") != episode_id:
        raise ValueError("子Agent返回分集编号错误")
    if value.get("input_sha256") != input_sha256:
        raise ValueError("子Agent返回未绑定当前输入")
    if value.get("status") not in {"PASS", "FAIL"}:
        raise ValueError("子Agent返回状态错误")
    if not isinstance(value.get("content"), str) or not isinstance(value.get("findings"), list):
        raise ValueError("子Agent返回内容类型错误")
    if value["status"] == "PASS" and action in {"WRITE_DRAFT", "ENHANCE", "REPAIR"} and not value["content"].strip():
        raise ValueError("写作类子Agent PASS但正文为空")
    if value["status"] == "FAIL" and not value["findings"]:
        raise ValueError("子Agent FAIL但没有问题说明")
    return value


def active_contract(cache_root: Path, episode_id: str, action: str, lease: str) -> dict[str, Any]:
    state = load(cache_root)
    episode = (state.get("episodes") or {}).get(episode_id) or {}
    active = (episode.get("leases") or {}).get(action)
    if not isinstance(active, dict) or active.get("lease") != lease:
        raise ValueError("子Agent结果租约无效")
    return active


def replace_complete_script(artifact: str, script: str) -> str:
    pattern = re.compile(
        r"(^##\s*完整剧本\s*\n)(.*?)(?=^#\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(artifact)
    if not match:
        raise ValueError("正式单集缺少完整剧本区")
    return artifact[:match.start(2)] + "\n" + script.strip() + "\n\n" + artifact[match.end(2):].lstrip("\n")


def review_source(action: str) -> str:
    return "dramatization" if action == "REVIEW_DRAMA" else "cold-read"


def commit_review(
    cache_root: Path,
    episode_id: str,
    action: str,
    lease: str,
    value: dict[str, Any],
) -> None:
    source = review_source(action)
    if value["status"] == "PASS":
        if value["findings"]:
            raise ValueError("复检PASS不得同时返回问题单")
        try:
            review = json.loads(value["content"])
        except json.JSONDecodeError as error:
            raise ValueError("复检PASS的content必须是对应gate可直接验收的JSON对象") from error
        if not isinstance(review, dict):
            raise ValueError("复检PASS内容必须是JSON对象")
        submission = cache_root / "child-results" / f"{episode_id}.{source}.submission.json"
        atomic_write(submission, json.dumps(review, ensure_ascii=False, indent=2) + "\n")
        receipt = (
            seal_dramatization(cache_root, episode_id, submission)
            if action == "REVIEW_DRAMA"
            else seal_cold_read(cache_root, episode_id, submission)
        )
        complete(cache_root, episode_id, action, lease, [receipt], "PASS")
        return

    try:
        metadata = json.loads(value["content"] or "{}")
    except json.JSONDecodeError as error:
        raise ValueError("复检FAIL的content必须是含rewrite_required的JSON对象") from error
    if not isinstance(metadata, dict) or set(metadata) - {"rewrite_required"}:
        raise ValueError("复检FAIL的content只允许包含rewrite_required")
    script = (cache_root / "enhanced-screenplays" / f"{episode_id}.md").read_text(encoding="utf-8").strip()
    finding = {
        "contract_version": FINDINGS_VERSION,
        "episode_id": episode_id,
        "source": source,
        "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "status": "FAIL",
        "rewrite_required": bool(metadata.get("rewrite_required")),
        "issues": value["findings"],
    }
    errors = validate_findings(finding, episode_id, script)
    if errors:
        raise ValueError("；".join(errors))
    target = cache_root / "review-findings" / f"{episode_id}.{source}.json"
    atomic_write(target, json.dumps(finding, ensure_ascii=False, indent=2) + "\n")
    complete(cache_root, episode_id, action, lease, [target], "FAIL")


def commit_repair(cache_root: Path, episode_id: str, lease: str, script: str) -> None:
    enhanced = cache_root / "enhanced-screenplays" / f"{episode_id}.md"
    formal = cache_root / "episodes" / f"{episode_id}.md"
    merged = cache_root / "merged-review-findings" / f"{episode_id}.json"
    baseline = cache_root / "repair-baselines" / f"{episode_id}.md"
    receipt = cache_root / "review-repair-receipts" / f"{episode_id}.json"
    original_enhanced = enhanced.read_text(encoding="utf-8")
    original_formal = formal.read_text(encoding="utf-8")
    atomic_write(baseline, original_enhanced.strip() + "\n")
    try:
        atomic_write(enhanced, script.strip() + "\n")
        atomic_write(formal, replace_complete_script(original_formal, script))
        value = verify_repair(cache_root, episode_id, baseline, merged)
        write_repair_receipt(receipt, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        complete(cache_root, episode_id, "REPAIR", lease, [enhanced, formal, receipt], "PASS")
    except BaseException:
        atomic_write(enhanced, original_enhanced)
        atomic_write(formal, original_formal)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("episode_id")
    parser.add_argument("action", choices=sorted(CHILD_ACTIONS))
    parser.add_argument("result", type=Path)
    parser.add_argument("--lease", required=True)
    args = parser.parse_args()
    try:
        active = active_contract(args.cache_root, args.episode_id, args.action, args.lease)
        value = validate(
            json.loads(args.result.read_text(encoding="utf-8")),
            args.episode_id,
            args.action,
            str(active.get("input_sha256") or ""),
        )
        if args.action in {"REVIEW_DRAMA", "REVIEW_COLD_READ"}:
            commit_review(args.cache_root, args.episode_id, args.action, args.lease, value)
            print("CHILD_REVIEW_COMMITTED")
            return 0 if value["status"] == "PASS" else 2
        if value["status"] == "FAIL":
            reason = "；".join(str(item) for item in value["findings"])
            fail(args.cache_root, args.episode_id, args.action, args.lease, reason, "content")
            print("CHILD_RESULT_RECORDED_FAIL")
            return 2
        if args.action == "WRITE_DRAFT":
            target = args.cache_root / "screenplay-drafts" / f"{args.episode_id}.md"
            atomic_write(target, value["content"].strip() + "\n")
            complete(args.cache_root, args.episode_id, args.action, args.lease, [target], "PASS")
            print("CHILD_RESULT_COMMITTED")
            return 0
        if args.action == "ENHANCE":
            target = args.cache_root / "enhanced-screenplays" / f"{args.episode_id}.md"
            atomic_write(target, value["content"].strip() + "\n")
            complete(args.cache_root, args.episode_id, args.action, args.lease, [target], "PASS")
            print("CHILD_RESULT_COMMITTED")
            return 0
        if args.action == "REPAIR":
            if value["findings"]:
                raise ValueError("局部修复PASS不得同时返回问题单")
            commit_repair(args.cache_root, args.episode_id, args.lease, value["content"])
            print("CHILD_REPAIR_COMMITTED")
            return 0
        target = args.cache_root / "child-results" / f"{args.episode_id}.{args.action}.json"
        atomic_write(target, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        print(f"CHILD_RESULT_STAGED: {target}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
