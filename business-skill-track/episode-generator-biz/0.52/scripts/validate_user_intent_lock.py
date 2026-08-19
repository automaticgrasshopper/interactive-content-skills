#!/usr/bin/env python3
"""Validate the minimal user-intent lock used by episode-generator 0.51."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "nextplay.user-intent-lock.v2"
REVIEW_VERSION = "nextplay.user-intent-review.v1"
ROOT_FIELDS = {
    "contract_version", "source_sha256", "resolution_status",
    "fixed_episode_count", "constraints", "conflicts", "resolutions",
}
CONSTRAINT_FIELDS = {
    "constraint_id", "statement", "scope", "required", "forbidden_literals",
}
SCOPES = {"global", "topology"}
FORBIDDEN_KEYS = {"node_count_hint", "node_count_suggestion", "episode_count_hint"}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def contract_binding(cache_root: Path) -> tuple[str, str]:
    contract, contract_sha, issues = validate_contract(cache_root)
    if issues:
        raise ValueError("；".join(issues))
    return str(contract["source_sha256"]), contract_sha


def validate_contract(cache_root: Path) -> tuple[dict[str, Any], str, list[str]]:
    issues: list[str] = []
    request_path = cache_root / "user-request.md"
    contract_path = cache_root / "user-intent-lock.json"
    if not request_path.is_file():
        return {}, "", ["缺少 user-request.md"]
    if not contract_path.is_file():
        return {}, "", ["缺少 user-intent-lock.json"]
    request_text = request_path.read_text(encoding="utf-8")
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, "", [f"用户意图合同不可读：{error}"]
    if not isinstance(contract, dict) or set(contract) != ROOT_FIELDS:
        return {}, "", ["用户意图合同根字段错误"]
    if contract.get("contract_version") != CONTRACT_VERSION:
        issues.append(f"用户意图合同版本错误：期望 {CONTRACT_VERSION}")
    source_sha = sha256_bytes(request_path.read_bytes())
    if contract.get("source_sha256") != source_sha:
        issues.append("用户意图合同未绑定当前 user-request.md")
    if contract.get("resolution_status") not in {"resolved", "needs-user"}:
        issues.append("用户意图 resolution_status 非法")
    fixed = contract.get("fixed_episode_count")
    if fixed is not None and (isinstance(fixed, bool) or not isinstance(fixed, int) or fixed < 1):
        issues.append("fixed_episode_count 必须是正整数或 null")

    serialized = canonical(contract)
    if any(key in serialized for key in FORBIDDEN_KEYS):
        issues.append("用户意图合同不得记录任何上游节点建议字段")

    constraints = contract.get("constraints")
    if not isinstance(constraints, list):
        issues.append("constraints 必须是数组")
        constraints = []
    ids: set[str] = set()
    fixed_statements = 0
    for index, item in enumerate(constraints, 1):
        if not isinstance(item, dict) or set(item) != CONSTRAINT_FIELDS:
            issues.append(f"用户约束第{index}项字段错误")
            continue
        constraint_id = str(item.get("constraint_id") or "")
        statement = str(item.get("statement") or "").strip()
        if not constraint_id.startswith("user-") or constraint_id in ids:
            issues.append(f"用户约束编号非法或重复：{constraint_id}")
        ids.add(constraint_id)
        if not statement:
            issues.append(f"用户约束缺少 statement：{constraint_id}")
        elif statement not in request_text:
            issues.append(f"用户约束不是 user-request.md 中的逐字原话：{constraint_id}")
        if item.get("required") is not True:
            issues.append(f"constraints 只保留 required=true 的硬约束：{constraint_id}")
        scopes = item.get("scope")
        if not isinstance(scopes, list) or not scopes:
            issues.append(f"用户约束 scope 非法：{constraint_id}")
        else:
            for scope in scopes:
                if scope not in SCOPES and not re.fullmatch(r"episode-\d{3}", str(scope)):
                    issues.append(f"用户约束 scope 非法：{constraint_id}/{scope}")
        forbidden = item.get("forbidden_literals")
        if not isinstance(forbidden, list) or any(not isinstance(x, str) or not x.strip() for x in forbidden):
            issues.append(f"forbidden_literals 必须是非空字符串数组：{constraint_id}")
        fixed_pattern = rf"(?:固定(?:为)?|必须(?:是|为|恰好)?|恰好)\s*{fixed}\s*集" if fixed is not None else None
        if fixed_pattern and statement in request_text and re.search(fixed_pattern, statement):
            fixed_statements += 1
    if fixed is not None and fixed_statements == 0:
        issues.append("fixed_episode_count 缺少用户明确固定N集的约束原话")

    conflicts = contract.get("conflicts")
    resolutions = contract.get("resolutions")
    if not isinstance(conflicts, list) or not isinstance(resolutions, list):
        issues.append("conflicts 和 resolutions 必须是数组")
    if contract.get("resolution_status") == "resolved" and conflicts:
        issues.append("resolved 合同不得保留未解决 conflicts")
    return contract, hashlib.sha256(canonical(contract).encode("utf-8")).hexdigest(), list(dict.fromkeys(issues))


def validate_user_intent_project(cache_root: Path) -> list[str]:
    """Recheck only explicit user locks against the frozen graph and episodes."""
    contract, contract_sha, issues = validate_contract(cache_root)
    if issues:
        return list(dict.fromkeys(issues))
    try:
        review = load_json(cache_root / "user-intent-review.json", "用户意图履约复检")
        artifact_sha = artifact_digest(cache_root)
        topology_text = (cache_root / "topology.md").read_text(encoding="utf-8")
        episode_texts = {
            path.stem: path.read_text(encoding="utf-8")
            for path in (cache_root / "episodes").glob("episode-*.md")
        }
        if contract.get("fixed_episode_count") is not None:
            from validate_topology import parse

            actual_count = len(parse(cache_root / "topology.md"))
            if actual_count != contract["fixed_episode_count"]:
                issues.append(
                    "用户固定集数未满足："
                    f"要求{contract['fixed_episode_count']}，实际{actual_count}"
                )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]

    if review.get("review_version") != REVIEW_VERSION:
        issues.append("用户意图履约复检版本错误")
    if review.get("source_sha256") != contract["source_sha256"]:
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
    active = list(contract["constraints"])
    if set(by_id) != {str(item["constraint_id"]) for item in active}:
        issues.append("用户意图履约复检约束集合与当前合同不一致")

    all_text = "\n".join([topology_text, *episode_texts.values()])
    for constraint in active:
        constraint_id = str(constraint["constraint_id"])
        item = by_id.get(constraint_id) or {}
        if item.get("satisfied") is not True:
            issues.append(f"用户要求未通过履约复检：{constraint_id}")
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("contract", "project"))
    parser.add_argument("cache_root", type=Path)
    args = parser.parse_args()
    if args.command == "project":
        issues = validate_user_intent_project(args.cache_root)
    else:
        contract, _, issues = validate_contract(args.cache_root)
        if contract.get("resolution_status") == "needs-user":
            issues.append("用户意图仍需用户解决冲突")
    if issues:
        for issue in dict.fromkeys(issues):
            print(f"FAIL: {issue}")
        return 1
    print("PASS: minimal user intent lock verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
