#!/usr/bin/env python3
"""Deterministically wrap one final screenplay in the nine-field private artifact."""

from __future__ import annotations

from execution_result import not_accepted

import argparse
import json
from pathlib import Path

from episode_artifact import atomic_write, predecessors
from validate_character_appearances import load_asset_catalog, mentioned_characters
from validate_topology import parse


def listed(values: list[str]) -> str:
    return "、".join(values) if values else "无"


def build(cache_root: Path, episode_id: str) -> str:
    nodes = parse(cache_root / "topology.md")
    if episode_id not in nodes:
        raise ValueError(f"冻结拓扑不存在分集：{episode_id}")
    node = nodes[episode_id]
    synopsis = json.loads(
        (cache_root / "episode-synopses" / f"{episode_id}.json").read_text(encoding="utf-8")
    )
    if synopsis.get("episode_id") != episode_id:
        raise ValueError("分集梗概编号错误")
    screenplay = (cache_root / "screenplays" / f"{episode_id}.md").read_text(encoding="utf-8").strip()
    if not screenplay:
        raise ValueError("完整剧本为空")
    catalog = load_asset_catalog(cache_root / "asset-catalog.json")
    characters = sorted(mentioned_characters(screenplay, catalog))
    scenes = sorted(name for name in catalog["scenes"] if name in screenplay)
    props = sorted(name for name in catalog["props"] if name in screenplay)
    incoming = predecessors(nodes)[episode_id]
    outgoing = list(node["successors"])
    choices = list(node["choices"])
    branch = bool(choices)
    options = "无" if not choices else "\n".join(
        f"- 选项编号：{index}\n  - 选项文字：{text}\n  - 目标分集编号：{target}"
        for index, (text, target) in enumerate(choices, 1)
    )
    if branch:
        default_next = choices[0][1]
    elif len(outgoing) == 1:
        default_next = outgoing[0]
    else:
        default_next = "无"
    return f"""# 分集编号
{episode_id}
# 分集标题
{node['title']}
# 分集剧本
## 单集梗概
{str(synopsis.get('synopsis') or '').strip()}
## 完整剧本
{screenplay}
# 剧本分析
## 本集冲突
{str(synopsis.get('conflict') or '').strip()}
## 前置节点编号列表
{listed(incoming)}
## 后续节点编号列表
{listed(outgoing)}
# 关联角色
{listed(characters)}
# 关联场景
{listed(scenes)}
# 关联道具
{listed(props)}
# 是否结局
{'是' if node['ending'] else '否'}
# 互动节点
## 是否为分支节点
{'是' if branch else '否'}
## 是否有选择问题
{'是' if branch else '否'}
## 选择问题
{str(node.get('question') or '').strip() if branch else '无'}
## 选项列表
{options}
## 默认下一分集编号
{default_next}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("episode_id")
    args = parser.parse_args()
    try:
        output = args.cache_root / "episodes" / f"{args.episode_id}.md"
        atomic_write(output, build(args.cache_root, args.episode_id))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return not_accepted(__file__)
    print(f"PASS: {output}")
    return 0


if __name__ == "__main__":
    from execution_result import run_cli
    raise SystemExit(run_cli(main, __file__))
