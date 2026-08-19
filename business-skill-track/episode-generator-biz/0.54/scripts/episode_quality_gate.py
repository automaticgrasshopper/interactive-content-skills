#!/usr/bin/env python3
"""Build and seal a small independent screenplay cold-read."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


PACKET_VERSION = "nextplay.episode-quality-packet.v1"
REVIEW_VERSION = "nextplay.episode-quality-review.v1"
RECEIPT_VERSION = "nextplay.episode-quality-receipt.v1"
CHECKS = [
    "concrete_action_chain",
    "situated_dialogue",
    "time_space_continuity",
    "no_meta_registry_or_summary",
    "stop_boundary_and_next_entry",
]
REFERENCE = Path(__file__).resolve().parents[1] / "references" / "episode-quality-review-lite.md"


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
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


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def packet_path(root: Path, episode_id: str) -> Path:
    return root / "episode-review-packets" / f"{episode_id}.json"


def build_packet(root: Path, episode_id: str) -> dict[str, Any]:
    screenplay_path = root / "screenplays" / f"{episode_id}.md"
    material_path = root / "episode-story-materials" / f"{episode_id}.json"
    structure_path = root / "episode-structure-receipts" / f"{episode_id}.json"
    screenplay = screenplay_path.read_text(encoding="utf-8").strip()
    material = json.loads(material_path.read_text(encoding="utf-8"))
    if not screenplay or material.get("episode_id") != episode_id:
        raise ValueError("独立复检输入不完整")
    return {
        "contract_version": PACKET_VERSION,
        "episode_id": episode_id,
        "screenplay_sha256": digest_text(screenplay),
        "story_material_sha256": digest(material_path),
        "structure_receipt_sha256": digest(structure_path),
        "reference_sha256": digest(REFERENCE),
        "required_checks": CHECKS,
        "story": material.get("story"),
        "stop_boundary": material.get("stop_boundary"),
        "screenplay": screenplay,
    }


def write_packet(root: Path, episode_id: str) -> Path:
    path = packet_path(root, episode_id)
    atomic_json(path, build_packet(root, episode_id))
    return path


def validate_review(packet: dict[str, Any], review: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    expected = {
        "contract_version", "episode_id", "screenplay_sha256", "reference_sha256",
        "covered_checks", "status", "issues",
    }
    if set(review) != expected:
        issues.append("复检字段不符合轻量合同")
    if review.get("contract_version") != REVIEW_VERSION:
        issues.append("复检合同版本错误")
    for key in ("episode_id", "screenplay_sha256", "reference_sha256"):
        if review.get(key) != packet.get(key):
            issues.append(f"复检未绑定当前{key}")
    if review.get("covered_checks") != CHECKS:
        issues.append("复检未完整覆盖五项检查")
    status = review.get("status")
    found = review.get("issues")
    if status not in {"PASS", "FAIL"} or not isinstance(found, list):
        issues.append("复检状态或问题列表非法")
        return issues
    if status == "PASS" and found:
        issues.append("PASS复检不得包含问题")
    if status == "FAIL" and not 1 <= len(found) <= 3:
        issues.append("FAIL复检必须给出一至三个关键问题")
    screenplay = str(packet.get("screenplay") or "")
    for index, item in enumerate(found, 1):
        if not isinstance(item, dict) or set(item) != {"category", "anchor", "reason"}:
            issues.append(f"问题{index}字段错误")
            continue
        anchor = str(item.get("anchor") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if item.get("category") not in CHECKS:
            issues.append(f"问题{index}分类不属于五项检查")
        if len(anchor) < 4 or anchor not in screenplay or len(reason) < 8:
            issues.append(f"问题{index}缺少当前正文锚点或有效原因")
    return issues


def seal(root: Path, episode_id: str, candidate: Path) -> Path:
    packet = build_packet(root, episode_id)
    stored = json.loads(packet_path(root, episode_id).read_text(encoding="utf-8"))
    if stored != packet:
        raise ValueError("复检材料包已失效")
    review = json.loads(candidate.read_text(encoding="utf-8"))
    errors = validate_review(packet, review)
    if errors:
        raise ValueError("；".join(errors))
    if review["status"] != "PASS":
        raise ValueError("独立冷读未通过；必须准备整集重写")
    receipt = {
        "contract_version": RECEIPT_VERSION,
        "episode_id": episode_id,
        "screenplay_sha256": packet["screenplay_sha256"],
        "packet_sha256": digest(packet_path(root, episode_id)),
        "reference_sha256": packet["reference_sha256"],
        "covered_checks": CHECKS,
        "status": "PASS",
    }
    path = root / "episode-quality-receipts" / f"{episode_id}.json"
    atomic_json(path, receipt)
    return path


def prepare_rewrite(root: Path, episode_id: str, candidate: Path) -> Path:
    packet = build_packet(root, episode_id)
    review = json.loads(candidate.read_text(encoding="utf-8"))
    errors = validate_review(packet, review)
    if errors:
        raise ValueError("；".join(errors))
    if review["status"] != "FAIL":
        raise ValueError("只有FAIL复检可以准备重写")
    base = root / "episode-writing-inputs" / f"{episode_id}.txt"
    findings = {
        "contract_version": "nextplay.episode-rewrite-findings.v1",
        "episode_id": episode_id,
        "base_input_sha256": digest(base),
        "failed_screenplay_sha256": packet["screenplay_sha256"],
        "issues": review["issues"],
        "status": "FAIL",
    }
    findings_path = root / "episode-review-findings" / f"{episode_id}.json"
    atomic_json(findings_path, findings)
    rewrite_path = root / "episode-rewrite-inputs" / f"{episode_id}.txt"
    atomic_text(rewrite_path,
        "REWRITE_INPUT_VERSION=nextplay.episode-rewrite-input.v1\n"
        f"BASE_INPUT_SHA256={findings['base_input_sha256']}\n"
        f"FAILED_SCREENPLAY_SHA256={findings['failed_screenplay_sha256']}\n\n"
        "<ORIGINAL_WRITING_INPUT>\n" + base.read_text(encoding="utf-8").strip() +
        "\n</ORIGINAL_WRITING_INPUT>\n\n<FAILED_SCREENPLAY>\n" + str(packet["screenplay"]).strip() +
        "\n</FAILED_SCREENPLAY>\n\n<REVIEW_ISSUES>\n" +
        json.dumps(review["issues"], ensure_ascii=False, indent=2) +
        "\n</REVIEW_ISSUES>\n",
    )
    return rewrite_path


def verify(root: Path, episode_id: str) -> list[str]:
    try:
        packet = build_packet(root, episode_id)
        path = root / "episode-quality-receipts" / f"{episode_id}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        expected = {
            "contract_version": RECEIPT_VERSION,
            "episode_id": episode_id,
            "screenplay_sha256": packet["screenplay_sha256"],
            "packet_sha256": digest(packet_path(root, episode_id)),
            "reference_sha256": packet["reference_sha256"],
            "covered_checks": CHECKS,
            "status": "PASS",
        }
        return [] if value == expected else ["独立复检回执已失效"]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("packet", "verify"):
        item = sub.add_parser(name); item.add_argument("cache_root", type=Path); item.add_argument("episode_id")
    for name in ("seal", "prepare-rewrite"):
        item = sub.add_parser(name); item.add_argument("cache_root", type=Path); item.add_argument("episode_id"); item.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "packet":
            print(write_packet(args.cache_root, args.episode_id))
        elif args.command == "seal":
            print(seal(args.cache_root, args.episode_id, args.candidate))
        elif args.command == "prepare-rewrite":
            print(prepare_rewrite(args.cache_root, args.episode_id, args.candidate))
        else:
            errors = verify(args.cache_root, args.episode_id)
            if errors:
                raise ValueError("；".join(errors))
            print("PASS")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
