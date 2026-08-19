#!/usr/bin/env python3
"""Build the private source used to create one coherent episode story material."""

from __future__ import annotations

from execution_result import not_accepted, refresh_route

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from episode_artifact import predecessors, section, subsection
from validate_topology import parse


CONTRACT_VERSION = "nextplay.episode-adaptation-source.v1"
EPISODE_ID = re.compile(r"episode-\d{3}")


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少{label}：{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须是JSON对象")
    return value


def ending_excerpt(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"直接前置尚无已放行正文：{path.stem}")
    text = path.read_text(encoding="utf-8")
    script = subsection(section(text, "分集剧本"), "完整剧本")
    blocks = [block.strip() for block in re.split(r"\n\s*\n", script) if block.strip()]
    return "\n\n".join(blocks[-4:])


def selected_edge(nodes: dict[str, dict[str, object]], source: str, target: str) -> str:
    for option_text, option_target in nodes[source]["choices"]:
        if option_target == target:
            return option_text
    return "默认推进"


def compact_fact(name: str, value: str, *, identity: bool = False) -> str:
    fact = str(value or "").strip()
    if fact.startswith(name):
        fact = fact[len(name):].lstrip()
    if identity:
        fact = re.sub(r"^(?:是|为|作为|担任|系)", "", fact).strip()
    else:
        fact = re.sub(r"^是", "", fact).strip()
    return fact


def adaptation_character_card(card: dict[str, Any]) -> dict[str, Any]:
    name = str(card.get("name") or "").strip()
    description = str(card.get("description") or card.get("public_role") or card.get("identity") or "").strip()
    identity = re.split(r"[。；]", description, maxsplit=1)[0]
    return {
        "name": name,
        "public_role": compact_fact(name, identity, identity=True),
        "display_description": description,
    }


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def build(cache_root: Path, episode_id: str) -> dict[str, Any]:
    if EPISODE_ID.fullmatch(episode_id) is None:
        raise ValueError(f"非法分集编号：{episode_id}")
    nodes = parse(cache_root / "topology.md")
    if episode_id not in nodes:
        raise ValueError(f"冻结拓扑不存在分集：{episode_id}")

    creative_brief = read_json(cache_root / "creative-brief.json", "最小创作输入")
    assets = read_json(cache_root / "asset-catalog.json", "资产目录")
    intent = read_json(cache_root / "user-intent-lock.json", "用户意图合同")
    synopsis = read_json(
        cache_root / "episode-synopses" / f"{episode_id}.json",
        "当前冻结梗概",
    )
    if synopsis.get("episode_id") != episode_id:
        raise ValueError(f"当前冻结梗概编号不一致：{episode_id}")

    current_corpus = json.dumps(synopsis, ensure_ascii=False)
    cast = []
    brief_assets = creative_brief.get("assets") if isinstance(creative_brief.get("assets"), dict) else {}
    for card in brief_assets.get("characters") or []:
        if not isinstance(card, dict):
            continue
        name = str(card.get("name") or "").strip()
        if name and name in current_corpus:
            cast.append(adaptation_character_card(card))

    incoming = predecessors(nodes)[episode_id]
    continuity = [
        {
            "from_episode": source,
            "entry_action": selected_edge(nodes, source, episode_id),
            "previous_ending": ending_excerpt(cache_root / "episodes" / f"{source}.md"),
        }
        for source in incoming
    ]

    successors = []
    for target in nodes[episode_id]["successors"]:
        target_synopsis = read_json(
            cache_root / "episode-synopses" / f"{target}.json",
            f"直接后续冻结梗概 {target}",
        )
        successors.append({
            "episode_id": target,
            "entry_action": selected_edge(nodes, episode_id, target),
            "title": target_synopsis.get("title"),
            "synopsis": target_synopsis.get("synopsis"),
            "conflict": target_synopsis.get("conflict"),
        })

    scoped_constraints = []
    for item in intent.get("constraints") or []:
        if not isinstance(item, dict):
            continue
        scope = [str(value) for value in item.get("scope") or []]
        if "global" in scope or episode_id in scope:
            scoped_constraints.append({
                "statement": item.get("statement"),
                "forbidden_literals": item.get("forbidden_literals") or [],
            })

    node = nodes[episode_id]
    return {
        "contract_version": CONTRACT_VERSION,
        "episode_id": episode_id,
        "title": node["title"],
        "current_story": synopsis.get("synopsis"),
        "current_conflict": synopsis.get("conflict"),
        "continuity": continuity,
        "current_interaction": {
            "interaction": node["interaction"],
            "question": node["question"],
            "options": [
                {"option_text": text, "target_episode_id": target}
                for text, target in node["choices"]
            ],
            "is_ending": node["ending"],
        },
        "direct_successors": successors,
        "cast": cast,
        "available_assets": {
            "scenes": assets.get("scenes") or [],
            "props": assets.get("props") or [],
        },
        "world_rules": [],
        "continuity_constraints": [],
        "user_constraints": scoped_constraints,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("episode_id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        atomic_write(args.output, build(args.cache_root, args.episode_id))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    print(f"PASS: {args.output}")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
