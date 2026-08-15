#!/usr/bin/env python3
"""Validate the private user-intent contract and its independent review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "nextplay.user-intent-lock.v1"
REVIEW_VERSION = "nextplay.user-intent-review.v1"
EPISODE_ID = re.compile(r"episode-\d{3}")
SHA256 = re.compile(r"[0-9a-f]{64}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少{label}：{path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须是对象")
    return value


def artifact_digest(cache_root: Path) -> str:
    topology = cache_root / "topology.md"
    episodes = sorted((cache_root / "episodes").glob("episode-*.md"))
    if not topology.is_file() or not episodes:
        raise ValueError("用户意图复检缺少冻结拓扑或分集正文")
    digest = hashlib.sha256()
    for path in [topology, *episodes]:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_contract(cache_root: Path) -> tuple[dict[str, Any], str, list[str]]:
    issues: list[str] = []
    source_path = cache_root / "user-request.md"
    contract_path = cache_root / "user-intent-lock.json"
    if not source_path.is_file() or not source_path.read_text(encoding="utf-8").strip():
        return {}, "", ["缺少非空用户要求源文件：user-request.md"]
    try:
        contract = load_json(contract_path, "用户意图合同")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {}, "", [str(error)]
    source_sha = sha256_bytes(source_path.read_bytes())
    if contract.get("contract_version") != CONTRACT_VERSION:
        issues.append("用户意图合同版本错误")
    if contract.get("source_sha256") != source_sha:
        issues.append("用户意图合同未绑定当前用户要求源文件")
    status = contract.get("resolution_status")
    conflicts = contract.get("conflicts")
    if status == "needs-user" or (isinstance(conflicts, list) and conflicts):
        issues.append("ASK_USER_REQUIRED：用户前后明确要求存在未解决冲突")
    elif status != "resolved":
        issues.append("用户意图合同状态必须为 resolved 或 needs-user")
    if not isinstance(conflicts, list):
        issues.append("用户意图合同 conflicts 必须是列表")
    if not isinstance(contract.get("resolutions"), list):
        issues.append("用户意图合同 resolutions 必须是列表")
    constraints = contract.get("constraints")
    if not isinstance(constraints, list):
        issues.append("用户意图合同 constraints 必须是列表")
        constraints = []
    seen: set[str] = set()
    for index, item in enumerate(constraints, start=1):
        if not isinstance(item, dict):
            issues.append(f"用户约束第{index}项必须是对象")
            continue
        constraint_id = str(item.get("constraint_id") or "")
        if not re.fullmatch(r"user-\d{3}", constraint_id) or constraint_id in seen:
            issues.append(f"用户约束编号非法或重复：{constraint_id or index}")
        seen.add(constraint_id)
        if len(str(item.get("statement") or "").strip()) < 2:
            issues.append(f"用户约束内容为空：{constraint_id}")
        scope = item.get("scope")
        if not isinstance(scope, list) or not scope:
            issues.append(f"用户约束范围为空：{constraint_id}")
        elif any(value not in {"global", "topology"} and EPISODE_ID.fullmatch(str(value)) is None for value in scope):
            issues.append(f"用户约束范围非法：{constraint_id}")
        if not isinstance(item.get("required"), bool):
            issues.append(f"用户约束 required 必须是布尔值：{constraint_id}")
        forbidden = item.get("forbidden_literals")
        if not isinstance(forbidden, list) or any(not isinstance(value, str) or not value for value in forbidden):
            issues.append(f"用户约束 forbidden_literals 非法：{constraint_id}")
    return contract, sha256_bytes(contract_path.read_bytes()), issues


def validate_user_intent_project(cache_root: Path) -> list[str]:
    contract, contract_sha, issues = validate_contract(cache_root)
    if issues:
        return list(dict.fromkeys(issues))
    try:
        review = load_json(cache_root / "user-intent-review.json", "用户意图履约复检")
        artifact_sha = artifact_digest(cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    source_sha = str(contract["source_sha256"])
    if review.get("review_version") != REVIEW_VERSION:
        issues.append("用户意图履约复检版本错误")
    if review.get("source_sha256") != source_sha:
        issues.append("用户意图履约复检未绑定当前用户要求")
    if review.get("contract_sha256") != contract_sha:
        issues.append("用户意图履约复检未绑定当前合同")
    if review.get("artifact_sha256") != artifact_sha:
        issues.append("用户意图履约复检已失效：冻结拓扑或正文发生变化")
    if review.get("issues") != []:
        issues.append("用户意图履约复检仍有未解决问题")
    review_items = review.get("constraints")
    if not isinstance(review_items, list):
        issues.append("用户意图履约复检缺少逐项覆盖")
        review_items = []
    by_id = {
        str(item.get("constraint_id")): item
        for item in review_items
        if isinstance(item, dict)
    }
    active = [item for item in contract["constraints"] if item.get("required") is True]
    expected_ids = {str(item["constraint_id"]) for item in active}
    if set(by_id) != expected_ids:
        issues.append("用户意图履约复检约束集合与当前合同不一致")
    topology_text = (cache_root / "topology.md").read_text(encoding="utf-8")
    episode_texts = {
        path.stem: path.read_text(encoding="utf-8")
        for path in (cache_root / "episodes").glob("episode-*.md")
    }
    all_text = "\n".join([topology_text, *episode_texts.values()])
    for constraint in active:
        constraint_id = str(constraint["constraint_id"])
        item = by_id.get(constraint_id) or {}
        if item.get("satisfied") is not True:
            issues.append(f"用户要求未通过独立复检：{constraint_id}")
        if len(str(item.get("explanation") or "").strip()) < 6:
            issues.append(f"用户要求缺少履约说明：{constraint_id}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            issues.append(f"用户要求缺少正文证据：{constraint_id}")
            continue
        allowed_scope = set(str(value) for value in constraint["scope"])
        for proof in evidence:
            if not isinstance(proof, dict):
                issues.append(f"用户要求证据格式错误：{constraint_id}")
                continue
            location = str(proof.get("location") or "")
            quote = str(proof.get("quote") or "").strip()
            if len(quote) < 4:
                issues.append(f"用户要求证据过短：{constraint_id}")
                continue
            haystack = topology_text if location == "topology" else episode_texts.get(location, "")
            if not haystack or quote not in haystack:
                issues.append(f"用户要求证据不存在：{constraint_id}/{location}")
            if "global" not in allowed_scope and location not in allowed_scope:
                issues.append(f"用户要求证据超出约束范围：{constraint_id}/{location}")
        for forbidden in constraint.get("forbidden_literals") or []:
            if forbidden in all_text:
                issues.append(f"出现用户明确禁止的内容：{constraint_id}")
    return list(dict.fromkeys(issues))


def contract_binding(cache_root: Path) -> tuple[str, str]:
    contract, contract_sha, issues = validate_contract(cache_root)
    if issues:
        raise ValueError("；".join(issues))
    return str(contract["source_sha256"]), contract_sha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("contract", "project"))
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "contract":
            _, _, issues = validate_contract(args.cache_root)
        else:
            issues = validate_user_intent_project(args.cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues = [str(error)]
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        return 1
    print(f"PASS: user intent {args.mode} verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
