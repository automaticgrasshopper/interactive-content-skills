#!/usr/bin/env python3
"""Validate coherent story material and export the only compact-draft input."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True


MATERIAL_VERSION = "nextplay.episode-story-material.v1"
SOURCE_VERSION = "nextplay.episode-adaptation-source.v1"
EPISODE_ID = re.compile(r"episode-\d{3}")
BANNED_TERMS = (
    "story_progression", "process_chain", "process_id", "beat_id",
    "action_proof", "result_proof", "evidence", "sha256",
    "情绪脊", "拓扑", "过程链", "举证", "验收字段",
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少{label}：{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须是JSON对象")
    return value


def validate(source: dict[str, Any], material: dict[str, Any], episode_id: str) -> list[str]:
    errors: list[str] = []
    if source.get("contract_version") != SOURCE_VERSION or source.get("episode_id") != episode_id:
        errors.append("单集适配源合同或编号错误")
    expected = {"contract_version", "episode_id", "source_sha256", "story", "stop_boundary"}
    if set(material) != expected:
        errors.append("单集故事材料字段错误")
    if material.get("contract_version") != MATERIAL_VERSION or material.get("episode_id") != episode_id:
        errors.append("单集故事材料合同或编号错误")
    if material.get("source_sha256") != sha256(canonical(source)):
        errors.append("单集故事材料未绑定当前适配源")
    story = str(material.get("story") or "").strip()
    boundary = str(material.get("stop_boundary") or "").strip()
    if len(story) < 120:
        errors.append("单集故事材料过短，尚未形成连续故事")
    if len([block for block in re.split(r"\n\s*\n", story) if block.strip()]) > 6:
        errors.append("单集故事材料被拆得过碎")
    if re.search(r"(?m)^\s*(?:#{1,6}|[-*+]\s|\d+[.)、]\s)", story):
        errors.append("单集故事材料不得使用标题或清单")
    if EPISODE_ID.search(story) or any(term in story for term in BANNED_TERMS):
        errors.append("单集故事材料泄露节点或验收结构")
    if not 12 <= len(boundary) <= 220 or "\n" in boundary:
        errors.append("停止边界必须是一句清楚的短说明")
    if EPISODE_ID.search(boundary) or any(term in boundary for term in BANNED_TERMS):
        errors.append("停止边界泄露节点或验收结构")
    return list(dict.fromkeys(errors))


def atomic_write_text(path: Path, value: str) -> None:
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
    parser.add_argument("source", type=Path)
    parser.add_argument("material", type=Path)
    parser.add_argument("episode_id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        source = read_json(args.source, "单集适配源")
        material = read_json(args.material, "单集故事材料")
        errors = validate(source, material, args.episode_id)
        if errors:
            raise ValueError("；".join(errors))
        text = (
            "<STORY>\n"
            + str(material["story"]).strip()
            + "\n</STORY>\n\n<CAST_CONTEXT>\n"
            + json.dumps(source.get("cast") or [], ensure_ascii=False, indent=2)
            + "\n</CAST_CONTEXT>\n\n<CAST_RULE>\n"
            + "公开身份只用于帮助观众自然认人；不得让人物自报抽象职能。知情与能力边界是不可越过的事实边界，不是必须说出口的台词。\n"
            + "</CAST_RULE>\n\n<STOP_BOUNDARY>\n"
            + str(material["stop_boundary"]).strip()
            + "\n</STOP_BOUNDARY>\n"
        )
        atomic_write_text(args.output, text)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
