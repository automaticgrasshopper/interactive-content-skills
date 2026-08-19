#!/usr/bin/env python3
"""Cheap deterministic tripwires for non-screenplay and repeated-template output."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


ABSTRACT_PLACEHOLDERS = (
    "按计划动手", "阻力很快出现", "根据现场反馈", "随反馈失效",
    "重新调整顺序", "把可用资源留给下一步", "新的状态已经形成",
    "尚未解决的问题", "让事情真的往前走", "现场会给答案",
    "代价没有消失，只是换了一个地方落下",
)
ROLE_TERMS = ("继承人", "决策者", "掌柜", "主理人", "主播", "招商主管", "负责人")
SCENE = re.compile(r"^【[^】]+】$")


def normalized_segments(script: str, characters: set[str]) -> set[str]:
    result: set[str] = set()
    for raw in re.split(r"\n+", script):
        value = re.sub(r"\s+", "", raw.strip())
        if not value or SCENE.fullmatch(value):
            continue
        for name in sorted(characters, key=len, reverse=True):
            value = value.replace(name, "<角色>")
        if len(value) >= 18:
            result.add(value)
    return result


def local_issues(script: str, characters: set[str]) -> list[str]:
    issues: list[str] = []
    found = [item for item in ABSTRACT_PLACEHOLDERS if item in script]
    if found:
        issues.append(f"正文含抽象占位或万能骨架：{found}")
    for line in (item.strip() for item in script.splitlines() if item.strip()):
        if "：" in line or SCENE.fullmatch(line):
            continue
        for character in characters:
            before_name = line.find(character)
            role_before = [term for term in ROLE_TERMS if term in line and line.find(term) < before_name]
            if before_name >= 0 and role_before:
                issues.append(f"人物身份采用前置人物卡登记句：{line[:80]}")
                break
            if character in line and re.search(rf"{re.escape(character)}.*(?:他|她)正是", line):
                issues.append(f"人物关系采用登记式解释：{line[:80]}")
                break
    if re.search(r"必须[^。！？]{0,40}也必须", script):
        issues.append("正文用双重‘必须’直接总结人物任务，未把压力落实为当前行动")
    return list(dict.fromkeys(issues))


def cross_episode_issues(cache_root: Path, episode_id: str, script: str, characters: set[str]) -> list[str]:
    current = normalized_segments(script, characters)
    if not current:
        return []
    issues: list[str] = []
    for path in sorted((cache_root / "screenplays").glob("episode-*.md")):
        if path.stem == episode_id:
            continue
        other = normalized_segments(path.read_text(encoding="utf-8"), characters)
        shared = sorted(current & other, key=len, reverse=True)
        if len(shared) >= 4 or any(any(marker in line for marker in ABSTRACT_PLACEHOLDERS) for line in shared):
            issues.append(
                f"正文与{path.stem}重复使用跨集模板句：{[line[:60] for line in shared[:4]]}"
            )
            break
    return issues


def validate_screenplay_quality(
    cache_root: Path,
    episode_id: str,
    script: str,
    catalog: dict[str, Any],
) -> list[str]:
    characters = set(catalog.get("characters") or set())
    return [
        *local_issues(script, characters),
        *cross_episode_issues(cache_root, episode_id, script, characters),
    ]
