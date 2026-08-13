#!/usr/bin/env python3
"""Assemble a writer-facing adaptation packet from frozen episode facts."""

from __future__ import annotations

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
from dramatization_gate import validate_plan
from validate_topology import parse


CONTRACT_VERSION = "nextplay.episode-writing-context.v2"
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


def relevant_names(names: list[str], corpus: str) -> list[str]:
    return [name for name in names if name in corpus]


def character_is_relevant(name: str, corpus: str) -> bool:
    if name in corpus:
        return True
    return len(name) >= 3 and name[-2:] in corpus


def compact_fact(name: str, value: str, *, identity: bool = False) -> str:
    fact = str(value or "").strip()
    if fact.startswith(name):
        fact = fact[len(name):].lstrip()
    if identity:
        fact = re.sub(r"^(?:是|为|作为|担任|系)", "", fact).strip()
    else:
        fact = re.sub(r"^是", "", fact).strip()
    return fact


def writer_character_card(card: dict[str, Any]) -> dict[str, Any]:
    name = str(card.get("name") or "").strip()
    return {
        "name": name,
        "role_fact": compact_fact(name, str(card.get("identity") or ""), identity=True),
        "connection_facts": [
            compact_fact(name, str(value or ""))
            for value in card.get("relationships") or []
        ],
        "current_want": card.get("current_desire"),
        "knowledge": card.get("knowledge_boundary") or [],
        "capability": card.get("capability_boundary") or [],
        "speech_style": card.get("voice"),
    }


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
            character_cards.append(writer_character_card(card))
    scene_names = relevant_names(list(assets.get("scenes") or []), corpus)
    prop_names = relevant_names(list(assets.get("props") or []), corpus)

    continuity = []
    for source in incoming[episode_id]:
        predecessor_plan = read_json(
            cache_root / "dramatization-plans" / f"{source}.json",
            f"直接前置场面展开计划 {source}",
        )
        source_beats = predecessor_plan.get("beats") or []
        continuity.append({
            "from_episode": source,
            "entry_action": selected_edge(nodes, source, episode_id),
            "previous_situation": str(source_beats[-1].get("end_state") or "") if source_beats else "",
            "previous_ending": ending_excerpt(cache_root / "episodes" / f"{source}.md"),
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

    story_progression = []
    for beat in beats:
        for process in beat.get("process_chain") or []:
            story_progression.append({
                "place": process.get("scene"),
                "character": process.get("actor"),
                "situation": process.get("trigger_or_basis"),
                "attempt": process.get("action"),
                "involving": process.get("object"),
                "complication_or_check": process.get("resistance_or_verification"),
                "change": process.get("result"),
            })

    packet = {
        "contract_version": CONTRACT_VERSION,
        "episode": {
            "episode_id": episode_id,
            "title": node["title"],
            "story": synopsis.get("synopsis"),
            "dramatic_problem": synopsis.get("conflict"),
            "opening_situation": [str(beat.get("start_state") or "") for beat in beats],
            "ending_situation": [str(beat.get("end_state") or "") for beat in beats],
            "interaction": node["interaction"],
            "is_ending": node["ending"],
        },
        "continuity": continuity,
        "ending_and_next_entry": {
            "choice_question": node["question"],
            "player_actions": [
                {"option_text": text, "target_episode_id": target}
                for text, target in node["choices"]
            ],
            "successor_episode_ids": node["successors"],
        },
        "cast": character_cards,
        "staging": {
            "available_scenes": scene_names,
            "available_props": prop_names,
        },
        "world": {
            "rules": run_basis.get("story", {}).get("world_rules") or [],
            "continuity_constraints": run_basis.get("story", {}).get("consistency_constraints") or [],
        },
        "story_progression": story_progression,
        "user_constraints": scoped_constraints,
        "adaptation_freedom": [
            "在不改变故事事实和结果的前提下，自由安排信息何时由动作、称呼、反应或对白自然显露。",
            "允许补充不产生新剧情事实的空间调度、声音、触感、天气、停顿、打断、失败尝试、表演反应和短转场。",
            "允许把多项事实合并进同一场行动或话轮，也允许先演异常再由人物追问和核验。",
            "story_progression只锁定因果，不规定正文段落、句式和逐项展示顺序。",
            "connection_facts只指导人物怎样称呼、配合、拒绝和反应，不要求在本集逐条说出关系名称；互动已经让观众看懂时不再解释。",
            "人物身份放进出场动作或自然职务称呼，不让已经认识的人在对白中互相声明职位。",
        ],
        "fixed_boundaries": [
            "只演当前分集事实，不解释情绪脊、拓扑、路线价值或生产字段。",
            "不提前演出无关路线、未来分集和未来结局。",
            "不新增正式角色、场景、道具、能力、世界规则、选择、边或结局。",
            "从opening_situation成立处开始，在ending_situation已经可见时结束。",
            "不得把本材料的字段名、清单顺序或原句改写成正文。",
        ],
    }
    leaked_terms = {
        "process_chain", "process_id", "beat_id", "proof", "evidence",
        "sha256", "required_end_states", "writing_boundaries",
        "identity", "relationships",
    }
    serialized = json.dumps(packet, ensure_ascii=False)
    leaked = sorted(term for term in leaked_terms if term in serialized)
    if leaked:
        raise ValueError("单集写作包泄露验收结构：" + "、".join(leaked))
    return packet


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
