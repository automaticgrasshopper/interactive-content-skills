#!/usr/bin/env python3
"""Assemble one read-only episode writing context from frozen artifacts."""

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

from episode_artifact import predecessors, section, subsection
from dramatization_gate import validate_plan
from validate_topology import parse


CONTRACT_VERSION = "nextplay.episode-writing-context.v1"
EPISODE_ID = re.compile(r"episode-\d{3}")


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少{label}：{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}必须是JSON对象")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def relevant_names(names: list[str], corpus: str) -> list[str]:
    return [name for name in names if name in corpus]


def character_is_relevant(name: str, corpus: str) -> bool:
    if name in corpus:
        return True
    return len(name) >= 3 and name[-2:] in corpus


def build(cache_root: Path, episode_id: str) -> dict[str, Any]:
    if EPISODE_ID.fullmatch(episode_id) is None:
        raise ValueError(f"非法分集编号：{episode_id}")

    topology_path = cache_root / "topology.md"
    run_basis_path = cache_root / "run-basis.json"
    assets_path = cache_root / "asset-catalog.json"
    synopsis_path = cache_root / "episode-synopses" / f"{episode_id}.json"
    plan_path = cache_root / "dramatization-plans" / f"{episode_id}.json"

    nodes = parse(topology_path)
    if episode_id not in nodes:
        raise ValueError(f"冻结拓扑不存在分集：{episode_id}")
    incoming = predecessors(nodes)
    run_basis = read_json(run_basis_path, "运行基础")
    assets = read_json(assets_path, "资产目录")
    synopsis = read_json(synopsis_path, "冻结梗概")
    plan, plan_errors = validate_plan(cache_root, episode_id)
    if plan_errors:
        raise ValueError("；".join(plan_errors))
    if synopsis.get("episode_id") != episode_id or plan.get("episode_id") != episode_id:
        raise ValueError(f"单集材料编号不一致：{episode_id}")

    beats = plan.get("beats")
    if not isinstance(beats, list) or not beats:
        raise ValueError(f"场面展开计划缺少事件：{episode_id}")
    node = nodes[episode_id]
    corpus = json.dumps({"synopsis": synopsis, "plan": plan}, ensure_ascii=False)

    character_cards = []
    for card in run_basis.get("characters") or []:
        if not isinstance(card, dict):
            continue
        name = str(card.get("name") or "")
        if character_is_relevant(name, corpus):
            character_cards.append(card)
    scene_names = relevant_names(list(assets.get("scenes") or []), corpus)
    prop_names = relevant_names(list(assets.get("props") or []), corpus)

    predecessor_evidence = []
    for source in incoming[episode_id]:
        predecessor_plan = read_json(
            cache_root / "dramatization-plans" / f"{source}.json",
            f"直接前置场面展开计划 {source}",
        )
        source_beats = predecessor_plan.get("beats") or []
        predecessor_evidence.append({
            "episode_id": source,
            "selected_entry_action": selected_edge(nodes, source, episode_id),
            "planned_end_state": str(source_beats[-1].get("end_state") or "") if source_beats else "",
            "actual_ending_excerpt": ending_excerpt(cache_root / "episodes" / f"{source}.md"),
        })

    scoped_constraints = []
    intent = read_json(cache_root / "user-intent-lock.json", "用户意图合同")
    for item in intent.get("constraints") or []:
        if not isinstance(item, dict):
            continue
        scope = [str(value) for value in item.get("scope") or []]
        if "global" in scope or episode_id in scope:
            scoped_constraints.append({
                "constraint_id": item.get("constraint_id"),
                "statement": item.get("statement"),
                "forbidden_literals": item.get("forbidden_literals") or [],
            })

    process_chain = []
    for beat in beats:
        for process in beat.get("process_chain") or []:
            process_chain.append(process)

    return {
        "contract_version": CONTRACT_VERSION,
        "episode_id": episode_id,
        "title": node["title"],
        "source_bindings": {
            "topology_sha256": file_sha256(topology_path),
            "run_basis_sha256": file_sha256(run_basis_path),
            "asset_catalog_sha256": file_sha256(assets_path),
            "synopsis_sha256": canonical_sha256(synopsis),
            "dramatization_plan_sha256": canonical_sha256(plan),
        },
        "node_contract": {
            "predecessors": incoming[episode_id],
            "successors": node["successors"],
            "choice_question": node["question"],
            "choices": [
                {"option_text": text, "target_episode_id": target}
                for text, target in node["choices"]
            ],
            "interaction": node["interaction"],
            "is_ending": node["ending"],
        },
        "predecessor_evidence": predecessor_evidence,
        "entry_state": [str(beat.get("start_state") or "") for beat in beats],
        "characters": character_cards,
        "scene_state": scene_names,
        "props": prop_names,
        "world_rules": run_basis.get("story", {}).get("world_rules") or [],
        "consistency_constraints": run_basis.get("story", {}).get("consistency_constraints") or [],
        "episode_obligation": {
            "frozen_synopsis": synopsis.get("synopsis"),
            "conflict": synopsis.get("conflict"),
            "dramatic_goals": [str(beat.get("dramatic_goal") or "") for beat in beats],
            "process_chain": process_chain,
        },
        "exit_state": {
            "required_end_states": [str(beat.get("end_state") or "") for beat in beats],
            "successor_episode_ids": node["successors"],
        },
        "user_constraints": scoped_constraints,
        "writing_boundaries": [
            "只演当前分集已经冻结的事实，不解释情绪脊、拓扑或路线价值。",
            "不得载入或提前演出无关路线、未来分集正文和未来结局。",
            "不得新增角色、场景、道具、能力、世界规则、选择、边或结局。",
            "正文必须从entry_state成立处开始，并停在exit_state已经可见处。",
            "过程链负责动作完整；人物对白只回应眼前的人、风险和行动。",
        ],
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("episode_id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        context = build(args.cache_root, args.episode_id)
        atomic_write(args.output, context)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    print(f"PASS: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
