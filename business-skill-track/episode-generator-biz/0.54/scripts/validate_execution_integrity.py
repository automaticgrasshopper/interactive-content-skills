#!/usr/bin/env python3
"""Reject cache-local executable source used to bypass generative actions."""

from __future__ import annotations

from pathlib import Path


SOURCE_SUFFIXES = {".py", ".sh", ".js", ".mjs", ".ts", ".rb", ".pl"}


def issues(cache_root: Path) -> list[str]:
    found: list[str] = []
    for path in cache_root.rglob("*"):
        if not path.is_file():
            continue
        relative = str(path.relative_to(cache_root))
        if path.suffix.lower() in SOURCE_SUFFIXES:
            found.append(relative)
            continue
        try:
            if path.read_bytes()[:2] == b"#!":
                found.append(relative)
        except OSError:
            continue
    return [f"缓存目录含未授权可执行源码：{sorted(found)}"] if found else []
