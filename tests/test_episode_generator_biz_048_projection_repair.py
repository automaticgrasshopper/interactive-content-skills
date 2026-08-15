import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "business-skill-track" / "episode-generator-biz" / "0.48" / "scripts"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def topology(successor="episode-002"):
    return f"""<!-- 拓扑合同：{{\"contract_version\":\"nextplay.episode-topology.v1\",\"resolved_node_count\":2,\"count_source\":\"causal-expansion\"}} -->

## episode-001 ｜ 开始
- 后续节点：{successor}
- 互动类型：普通剧情
- 结局：否

## episode-002 ｜ 结束
- 后续节点：无
- 互动类型：主要正式结局
- 结局：是
"""


def make_fixture(root, *, wrong_mapping=False, broken_edge=False):
    mainline = {
        "contract_version": "nextplay.episode-mainline-story.v1",
        "title": "测试",
        "complete_story": "第一段原文。\n\n第二段原文。",
        "expected_ending_title": "结束",
    }
    write_json(root / "mainline-story.json", mainline)
    decomposition = {
        "contract_version": "nextplay.mainline-decomposition.v1",
        "mainline_sha256": hashlib.sha256(canonical(mainline).encode()).hexdigest(),
        "segments": [
            {"segment_id": "mainline-001", "title": "开始", "source_text": "第一段原文。"},
            {"segment_id": "mainline-002", "title": "结束", "source_text": "第二段原文。"},
        ],
    }
    write_json(root / "mainline-decomposition.json", decomposition)
    mapping = [
        {"segment_id": "mainline-001", "episode_id": "episode-002" if wrong_mapping else "episode-001"},
        {"segment_id": "mainline-002", "episode_id": "episode-001" if wrong_mapping else "episode-002"},
    ]
    write_json(root / "mainline-path.json", {"contract_version": "nextplay.mainline-path.v1", "path": mapping})
    (root / "topology.md").write_text(
        topology("episode-099" if broken_edge else "episode-002"), encoding="utf-8"
    )
    write_json(root / "route-duration.json", {
        "contract_version": "nextplay.route-duration.v1",
        "unit": "minutes",
        "duration_limit_minutes": 60,
        "mainline_path": ["episode-002", "episode-001"] if wrong_mapping else ["episode-001", "episode-002"],
        "node_minutes": {"episode-001": 1, "episode-002": 1},
        "paths": [{"ending_id": "episode-002", "node_ids": ["episode-001", "episode-002"], "total_minutes": 2}],
    })
    write_json(root / "episode-synopses" / "episode-001.json", {"synopsis": "第一段原文。"})
    write_json(root / "episode-synopses" / "episode-002.json", {"synopsis": "第二段原文。"})


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


def load_script_module(name):
    spec = importlib.util.spec_from_file_location(f"episode_048_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class ProjectionRepairTests(unittest.TestCase):
    def test_topology_rejects_choice_order_different_from_successor_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "topology.md").write_text("""<!-- 拓扑合同：{\"contract_version\":\"nextplay.episode-topology.v1\",\"resolved_node_count\":3,\"count_source\":\"causal-expansion\"} -->

## episode-001 ｜ 选择
- 后续节点：episode-002、episode-003
- 互动类型：关键选择
- 结局：否
- 选择问题：往哪走？
- 选择：走右边 → episode-003
- 选择：走左边 → episode-002

## episode-002 ｜ 左边
- 后续节点：无
- 互动类型：独立小结局
- 结局：是

## episode-003 ｜ 右边
- 后续节点：无
- 互动类型：独立小结局
- 结局：是
""", encoding="utf-8")
            result = run("validate_topology.py", root / "topology.md")
            self.assertEqual(result.returncode, 1)
            self.assertIn("选择目标与后继不一致", result.stdout)

    def test_emotional_movement_accepts_maximum_duration_wording(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_json(root / "stage-two-input.json", {"story": {"duration": "最多60分钟"}})
            phases = []
            for name in ("起", "承", "转", "合"):
                phases.append({
                    "phase": name,
                    "current": {"v": 0, "a": 0, "d": 0},
                    "target": {"v": 0.2, "a": 0.2, "d": 0.2},
                    "reality": {"v": -0.2, "a": 0.3, "d": -0.1},
                    "catalyst": "事件迫使人物立即采取下一步行动",
                    "audience_known_risk": "观众知道拖延将导致当前机会永久消失",
                    "candidate_fissures": ["人物必须在继续与离开之间作出决定"],
                })
            write_json(root / "movement.json", {
                "contract_version": "nextplay.unnumbered-emotional-movement.v1",
                "scale": {
                    "minimum_legal_path_length": 2,
                    "route_duration_limit_minutes": 60,
                    "interaction_min": 1,
                    "interaction_max": 4,
                    "source": "duration-and-causal-capacity",
                },
                "phases": phases,
            })
            result = run(
                "validate_emotional_movement.py",
                root / "movement.json",
                "--stage-two-input",
                root / "stage-two-input.json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_episode_object_returns_complete_business_record(self):
        module = load_script_module("assemble_business_output")
        text = """# 分集编号

episode-001

# 分集标题

开始

# 分集剧本

## 单集梗概

人物完成当前行动并面对下一步。

## 完整剧本

【房间·白昼·内】

甲推开门。

甲：开始吧。

# 剧本分析

## 本集冲突

甲必须进入房间。

## 前置节点编号列表

无

## 后续节点编号列表

episode-002

# 关联角色

甲

# 关联场景

房间

# 关联道具

无

# 是否结局

否

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

episode-002
"""
        node = {"title": "开始", "choices": [], "successors": ["episode-002"]}
        result = module.episode_object("episode-001", node, text)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["分集编号"], "episode-001")
        self.assertEqual(result["分集剧本"]["完整剧本"], "【房间·白昼·内】\n\n甲推开门。\n\n甲：开始吧。")

    def test_valid_projection_passes_both_phases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            make_fixture(root)
            self.assertEqual(run("validate_mainline_projection.py", root, "--topology-only").returncode, 0)
            self.assertEqual(run("validate_mainline_projection.py", root).returncode, 0)

    def test_safe_repair_recovers_mapping_from_verbatim_synopses(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            make_fixture(root, wrong_mapping=True)
            result = run("repair_mainline_projection.py", root, "--apply")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"status": "REPAIRED"', result.stdout)
            repaired = json.loads((root / "mainline-path.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [item["episode_id"] for item in repaired["path"]],
                ["episode-001", "episode-002"],
            )
            self.assertEqual(run("validate_mainline_projection.py", root).returncode, 0)

    def test_broken_topology_requests_local_reprojection_without_guessing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            make_fixture(root, broken_edge=True)
            original = (root / "mainline-path.json").read_bytes()
            result = run("repair_mainline_projection.py", root, "--apply")
            self.assertEqual(result.returncode, 2)
            self.assertIn('"status": "REPROJECT_REQUIRED"', result.stdout)
            self.assertEqual(
                json.loads(result.stdout)["regenerate_only"],
                ["topology.md", "mainline-path.json", "route-duration.json"],
            )
            self.assertEqual((root / "mainline-path.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
