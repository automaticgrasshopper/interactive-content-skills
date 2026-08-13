#!/usr/bin/env python3
"""Seal the complete script set and block stale business/route projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from completion_gate import validate_receipt
from dramatization_gate import verify_project as verify_dramatization_project
from episode_artifact import atomic_write, section, subsection
from episode_quality_gate import verify_project as verify_quality_project
from synopsis_set_gate import packet as synopsis_set_packet, verify as verify_synopsis_set
from validate_topology import parse


CONTRACT_VERSION = "nextplay.episode-stage-three-release.v2"
SKILL_VERSION = "episode-generator-biz/0.27"
RELEASE_NAME = "stage-three-release.json"
REVIEW_NAME = "project-release-review.json"
REQUIRED_CHECKS = [
    "全集因果连续",
    "核心目标兑现",
    "情绪轨迹兑现",
    "全部结局兑现",
    "题材期待兑现",
    "人话与对白一致性",
]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def read_episode(cache_root: Path, episode_id: str) -> tuple[str, str, str]:
    path = cache_root / "episodes" / f"{episode_id}.md"
    if not path.is_file():
        raise ValueError(f"缺少分集正文：{episode_id}")
    raw = path.read_bytes()
    artifact = raw.decode("utf-8").strip()
    full_script = subsection(section(artifact, "分集剧本"), "完整剧本")
    if not full_script:
        raise ValueError(f"完整剧本为空：{episode_id}")
    return sha256_text(artifact), sha256_text(full_script), full_script


def build_packet(cache_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    errors.extend(verify_synopsis_set(cache_root))
    errors.extend(verify_dramatization_project(cache_root))
    errors.extend(verify_quality_project(cache_root))
    if errors:
        raise ValueError("阶段三逐集门禁未全部通过：" + "；".join(dict.fromkeys(errors)))
    topology_path = cache_root / "topology.md"
    nodes = parse(topology_path)
    manifest: list[dict[str, Any]] = []
    scripts: dict[str, str] = {}
    for episode_id, node in nodes.items():
        artifact_sha, full_script_sha, full_script = read_episode(cache_root, episode_id)
        manifest.append({
            "episode_id": episode_id,
            "episode_artifact_sha256": artifact_sha,
            "full_script_sha256": full_script_sha,
            "ending": bool(node["ending"]),
        })
        scripts[episode_id] = full_script
    synopsis_packet = synopsis_set_packet(cache_root, allow_scripts=True)
    return {
        "contract_version": CONTRACT_VERSION,
        "skill_version": SKILL_VERSION,
        "topology_sha256": sha256_bytes(topology_path.read_bytes()),
        "synopsis_set_sha256": synopsis_packet["synopsis_set_sha256"],
        "episode_count": len(manifest),
        "script_manifest": manifest,
        "script_set_sha256": canonical_sha(manifest),
        "required_checks": REQUIRED_CHECKS,
        "ending_episode_ids": [item["episode_id"] for item in manifest if item["ending"]],
        "scripts": scripts,
    }


def validate_review(packet: dict[str, Any], review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "contract_version", "topology_sha256", "synopsis_set_sha256",
        "episode_count", "script_set_sha256", "required_checks",
    ):
        if review.get(key) != packet.get(key):
            errors.append(f"项目级复检未绑定当前剧本集合：{key}")
    if review.get("issues") != []:
        errors.append("项目级复检仍有未解决问题")
    checks = review.get("checks")
    if not isinstance(checks, list):
        return errors + ["项目级复检缺少checks"]
    by_name = {
        str(item.get("check")): item
        for item in checks if isinstance(item, dict) and item.get("check")
    }
    scripts = packet["scripts"]
    ending_ids = set(packet["ending_episode_ids"])
    covered_endings: set[str] = set()
    all_episode_ids = set(scripts)
    human_speech_kinds: dict[str, set[str]] = {episode_id: set() for episode_id in all_episode_ids}
    for check in REQUIRED_CHECKS:
        item = by_name.get(check) or {}
        if str(item.get("conclusion") or "") != "PASS":
            errors.append(f"项目级复检未通过：{check}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"项目级复检缺少证据：{check}")
            continue
        for proof_item in evidence:
            if not isinstance(proof_item, dict):
                errors.append(f"项目级复检证据格式错误：{check}")
                continue
            episode_id = str(proof_item.get("episode_id") or "")
            proof = str(proof_item.get("proof") or "").strip()
            if episode_id not in scripts or len(proof) < 6 or proof not in scripts[episode_id]:
                errors.append(f"项目级复检证据不属于当前完整剧本：{check}/{episode_id}")
            if check == "全部结局兑现" and episode_id in ending_ids:
                covered_endings.add(episode_id)
            if check == "人话与对白一致性" and episode_id in all_episode_ids:
                kind = str(proof_item.get("kind") or "")
                if kind not in {"narration", "dialogue"}:
                    errors.append(f"人话复检证据缺少有效kind：{episode_id}")
                else:
                    is_dialogue = bool(re.match(r"^[^：\n]{1,20}：", proof))
                    if (kind == "dialogue") != is_dialogue:
                        errors.append(f"人话复检证据类型与正文不符：{episode_id}/{kind}")
                    else:
                        human_speech_kinds[episode_id].add(kind)
    if covered_endings != ending_ids:
        errors.append("全部结局兑现证据未覆盖每个结局节点")
    missing_human = [
        episode_id for episode_id, kinds in human_speech_kinds.items()
        if kinds != {"narration", "dialogue"}
    ]
    if missing_human:
        errors.append("人话与对白一致性未逐集覆盖叙述和对白：" + "、".join(sorted(missing_human)))
    return list(dict.fromkeys(errors))


def release_path(cache_root: Path) -> Path:
    return cache_root / RELEASE_NAME


def seal(cache_root: Path, review_path: Path) -> Path:
    packet = build_packet(cache_root)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    errors = validate_review(packet, review)
    if errors:
        raise ValueError("；".join(errors))
    keys = (
        "contract_version", "skill_version", "topology_sha256",
        "synopsis_set_sha256", "episode_count", "script_manifest",
        "script_set_sha256", "required_checks", "ending_episode_ids",
    )
    receipt = {key: packet[key] for key in keys}
    receipt["checks"] = review["checks"]
    receipt["issues"] = []
    atomic_write(
        cache_root / REVIEW_NAME,
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
    )
    output = release_path(cache_root)
    atomic_write(output, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return output


def verify(cache_root: Path) -> list[str]:
    try:
        packet = build_packet(cache_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]
    path = release_path(cache_root)
    if not path.is_file():
        return ["缺少当前有效的阶段三统一放行凭证"]
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["阶段三统一放行凭证不可读取"]
    errors = validate_review(packet, receipt)
    for key in ("script_manifest", "ending_episode_ids"):
        if receipt.get(key) != packet.get(key):
            errors.append(f"阶段三统一放行凭证已失效：{key}")
    return list(dict.fromkeys(errors))


def business_scripts(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    episodes = data.get("分集列表") if isinstance(data, dict) else None
    if not isinstance(episodes, list):
        raise ValueError("业务JSON缺少分集列表")
    result: dict[str, str] = {}
    for episode in episodes:
        episode_id = str((episode or {}).get("分集编号") or "")
        script = str((((episode or {}).get("分集剧本") or {}).get("完整剧本")) or "").strip()
        if not episode_id or not script or episode_id in result:
            raise ValueError(f"业务JSON分集编号或完整剧本错误：{episode_id}")
        result[episode_id] = script
    return result


def _route_candidates(value: Any, episode_id: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        identifiers = {
            str(value.get(key) or "")
            for key in ("id", "key", "client_key", "episode_key", "episode_ref")
        }
        content = value.get("content")
        if episode_id in identifiers and isinstance(content, dict):
            script = content.get("script")
            if isinstance(script, dict) and isinstance(script.get("text"), str):
                found.append(script["text"].strip())
        for child in value.values():
            found.extend(_route_candidates(child, episode_id))
    elif isinstance(value, list):
        for child in value:
            found.extend(_route_candidates(child, episode_id))
    return found


def verify_projection(
    cache_root: Path,
    business_path: Path,
    route_path: Path,
    completion_receipt_path: Path,
) -> list[str]:
    errors = verify(cache_root)
    if errors:
        return errors
    try:
        release = json.loads(release_path(cache_root).read_text(encoding="utf-8"))
        expected = {
            item["episode_id"]: item["full_script_sha256"]
            for item in release["script_manifest"]
        }
        biz_scripts = business_scripts(business_path)
        route = json.loads(route_path.read_text(encoding="utf-8"))
        for episode_id, expected_sha in expected.items():
            biz = biz_scripts.get(episode_id)
            if biz is None or sha256_text(biz) != expected_sha:
                errors.append(f"业务JSON完整剧本与阶段三放行不一致：{episode_id}")
            candidates = _route_candidates(route, episode_id)
            matching = [text for text in candidates if sha256_text(text) == expected_sha]
            if len(matching) != 1:
                errors.append(f"route未唯一投影当前完整剧本：{episode_id}")
        if set(biz_scripts) != set(expected):
            errors.append("业务JSON分集集合与阶段三放行不一致")
        from assemble_business_output import BUSINESS_SKILL_VERSION
        errors.extend(validate_receipt(
            completion_receipt_path,
            cache_root,
            business_path,
            cache_root / "asset-catalog.json",
            cache_root / "character-introductions.json",
            cache_root / "emotional-spine.json",
            BUSINESS_SKILL_VERSION,
        ))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    packet_parser = subs.add_parser("packet")
    packet_parser.add_argument("cache_root", type=Path)
    packet_parser.add_argument("--output", type=Path)
    seal_parser = subs.add_parser("seal")
    seal_parser.add_argument("cache_root", type=Path)
    seal_parser.add_argument("review", type=Path)
    verify_parser = subs.add_parser("verify")
    verify_parser.add_argument("cache_root", type=Path)
    projection_parser = subs.add_parser("verify-projection")
    projection_parser.add_argument("cache_root", type=Path)
    projection_parser.add_argument("business_json", type=Path)
    projection_parser.add_argument("route_json", type=Path)
    projection_parser.add_argument("completion_receipt", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "packet":
            packet = build_packet(args.cache_root)
            text = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                atomic_write(args.output, text)
                print(f"PASS: {args.output}")
            else:
                print(text, end="")
        elif args.command == "seal":
            print(f"PASS: {seal(args.cache_root, args.review)}")
        elif args.command == "verify":
            errors = verify(args.cache_root)
            if errors:
                raise ValueError("；".join(errors))
            print("PASS: current script set has one valid stage-three release")
        else:
            errors = verify_projection(
                args.cache_root,
                args.business_json,
                args.route_json,
                args.completion_receipt,
            )
            if errors:
                raise ValueError("；".join(errors))
            print("PASS: business JSON, completion receipt, and route uniquely match the released scripts")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
