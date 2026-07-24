from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "skills" / "episode-generator" / "scripts"


def load_module(name: str):
    path = SCRIPT_ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(SCRIPT_ROOT))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class EpisodeScriptTests(unittest.TestCase):
    def test_emotional_topology_accepts_reachable_choice_endings(self) -> None:
        module = load_module("validate_emotional_topology")
        topology = """## episode-001｜抉择
- 互动类型：关键选择
- 结局：否
- 后续节点：episode-002、episode-003
- 选择：推开东门 → episode-002
- 选择：推开西门 → episode-003

## episode-002｜东门
- 互动类型：正式结局
- 结局：是
- 后续节点：无

## episode-003｜西门
- 互动类型：正式结局
- 结局：是
- 后续节点：无
"""
        directory = Path(tempfile.mkdtemp())
        topology_path = directory / "topology.md"
        topology_path.write_text(topology, encoding="utf-8")
        self.assertEqual(
            module.validate_emotional_topology(topology_path, None),
            [],
        )

    def test_quality_gate_packet_is_bound_to_current_skill(self) -> None:
        module = load_module("episode_quality_gate")
        directory = Path(tempfile.mkdtemp())
        (directory / "episodes").mkdir()
        (directory / "episodes" / "episode-001.md").write_text(
            """# 分集编号

episode-001

# 分集标题

开场

# 分集剧本

## 单集梗概

甲进门。

## 完整剧本

【旧屋·夜·内】

甲推开门，看见灯还亮着。

甲：我回来了。

# 剧本分析

## 本集冲突

甲确认屋内情况。

## 前置节点编号列表

无

## 后续节点编号列表

无

# 关联角色

甲

# 关联场景

旧屋

# 关联道具

无

# 是否结局

是

# 互动节点

## 是否为分支节点

否

## 是否有选择问题

否

## 选择问题

无

## 选项列表

无

## 默认下一分集编号

无
""",
            encoding="utf-8",
        )
        (directory / "assets.json").write_text(
            json.dumps(
                {"characters": ["甲"], "scenes": ["旧屋"], "props": []},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (directory / "topology.md").write_text(
            "## episode-001｜开场\n- 互动类型：正式结局\n- 结局：是\n- 后续节点：无\n",
            encoding="utf-8",
        )
        packet = module.build_packet(directory, "episode-001")
        self.assertEqual(packet["skill_version"], "v0.1.47")
        self.assertIn("甲：我回来了。", packet["script"])
        self.assertIn("七项完整覆盖", packet["reference"])


if __name__ == "__main__":
    unittest.main()
