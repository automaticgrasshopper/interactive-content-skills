import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from action_contracts import GENERATIVE_ACTIONS, REVIEW_ACTIONS, TRANSITIONS
from build_episode_artifact import build as build_episode_artifact
from episode_quality_gate import CHECKS, REVIEW_VERSION, validate_review
from validate_execution_integrity import issues as execution_integrity_issues
from validate_screenplay_quality import cross_episode_issues, local_issues


BAD_SCRIPT = """【西北拌面王后厨·日·内】
返乡接手老面馆的继承人、七天保店行动的决策者马小勺把店钥匙攥进掌心。
马小勺抬头看向父亲，接店这件事已经没有退路。
他必须在七天内保住面馆，也必须决定怎样面对配方旧债。
守着老招牌多年的掌柜马满仓扶住灶台，他正是马小勺必须面对的父亲。
马小勺：先别急着下结论，眼前哪一步能让事情真的往前走？
马满仓：先做，现场会给答案；做错了，也得当场认。
马小勺按计划动手，阻力很快出现；周围的声音由嘈杂转为安静，原先的判断随反馈失效。
马小勺停下，重新调整顺序，把可用资源留给下一步。
门外的提示声响起，新的状态已经形成，众人的视线同时转向尚未解决的问题。"""


class WritingChainTests(unittest.TestCase):
    def test_single_full_writer_plus_independent_light_review(self):
        self.assertEqual(GENERATIVE_ACTIONS, {"WRITE_EPISODE", "REVIEW_EPISODE"})
        self.assertEqual(REVIEW_ACTIONS, {"REVIEW_EPISODE"})
        self.assertEqual(
            " -> ".join(next(iter(step)) for step in TRANSITIONS.values()),
            "ADAPT -> WRITE_EPISODE -> VALIDATE_STRUCTURE -> REVIEW_EPISODE -> ACCEPT_EPISODE",
        )

    def test_obsolete_draft_and_enhancer_modules_are_absent(self):
        for relative in (
            "scripts/build_enhancer_input.py",
            "scripts/validate_compact_draft.py",
            "references/compact-draft-writer.md",
            "references/vimax-script-enhancer.md",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)
        self.assertTrue((ROOT / "references/vimax-screenwriter.md").is_file())
        self.assertTrue((ROOT / "references/episode-quality-review-lite.md").is_file())

    def test_main_skill_stays_small(self):
        self.assertLess(len((ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines()), 200)

    def test_no_subtask_contract_survives(self):
        banned = ("子Agent", "子任务", "subagent", "fork_turns", "隔离子", "WRITE_DRAFT", "VALIDATE_DRAFT")
        for folder in (ROOT / "references", ROOT / "scripts"):
            for path in folder.glob("*"):
                if path.is_file():
                    text = path.read_text(encoding="utf-8")
                    for term in banned:
                        self.assertNotIn(term, text, f"{term}: {path.name}")

    def test_reported_bad_screenplay_is_rejected(self):
        found = local_issues(BAD_SCRIPT, {"马小勺", "马满仓"})
        self.assertTrue(any("万能骨架" in issue for issue in found), found)
        self.assertTrue(any("人物卡登记句" in issue or "登记式解释" in issue for issue in found), found)
        self.assertTrue(any("双重" in issue for issue in found), found)

    def test_concrete_screenplay_does_not_trigger_template_tripwire(self):
        script = """【西北拌面王后厨·午·内】
面锅白沫漫过锅沿。马小勺拧死燃气阀，把滑到过道中央的油桶踢回墙边。
马小勺：爸，手给我。先出去。
马满仓推开他的手，抓起漏勺去捞锅里的面。漏勺碰到锅沿，当啷落地。
马小勺用湿布垫住锅耳，把锅拖离灶眼。传菜窗又塞进三张单子。
马满仓：停火，客人就散了。
马小勺撕下最上面一张单，把余下两张退回窗口。
马小勺：这一碗我做。做不出来，今天就关门。
马满仓盯着被他留下的那张红油拌面单，终于松开灶台。"""
        self.assertEqual(local_issues(script, {"马小勺", "马满仓"}), [])

    def test_cross_episode_template_reuse_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            screenplays = root / "screenplays"
            screenplays.mkdir()
            repeated = "\n".join(f"马小勺把第{i}张单据放到灶台边等待父亲回应。" for i in range(1, 5))
            (screenplays / "episode-001.md").write_text(repeated, encoding="utf-8")
            self.assertTrue(cross_episode_issues(root, "episode-002", repeated, {"马小勺"}))

    def test_cache_local_program_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "run_all_episodes.py").write_text("print('template')", encoding="utf-8")
            self.assertTrue(execution_integrity_issues(root))

    def test_light_review_requires_current_binding_and_valid_category(self):
        packet = {
            "episode_id": "episode-001",
            "screenplay_sha256": "screenplay",
            "reference_sha256": "reference",
            "screenplay": "马小勺把锅拖离灶眼，白沫停止外溢。",
        }
        review = {
            "contract_version": REVIEW_VERSION,
            "episode_id": "episode-001",
            "screenplay_sha256": "screenplay",
            "reference_sha256": "reference",
            "covered_checks": CHECKS,
            "status": "FAIL",
            "issues": [{
                "category": "invented_check",
                "anchor": "马小勺把锅拖离灶眼",
                "reason": "动作之后没有形成可见的现场反馈。",
            }],
        }
        self.assertTrue(any("分类" in issue for issue in validate_review(packet, review)))

    def test_formal_episode_wrapper_is_deterministic(self):
        topology = """<!-- 拓扑合同：{\"contract_version\":\"nextplay.episode-topology.v1\",\"resolved_node_count\":2,\"count_source\":\"causal-expansion\"} -->
## episode-001｜开门
- 后续节点：episode-002
- 互动类型：无
- 选择问题：无
- 结局：否

## episode-002｜收店
- 后续节点：无
- 互动类型：无
- 选择问题：无
- 结局：是
"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "topology.md").write_text(topology, encoding="utf-8")
            (root / "asset-catalog.json").write_text(
                '{"contract_version":"nextplay.episode-assets.v1","characters":["马小勺"],"scenes":["西北拌面王后厨"],"props":["钥匙"],"optional_characters":[],"character_aliases":{"马小勺":[]}}',
                encoding="utf-8",
            )
            (root / "episode-synopses").mkdir()
            (root / "episode-synopses/episode-001.json").write_text(
                '{"episode_id":"episode-001","synopsis":"马小勺接过钥匙并决定先保住灶火。","conflict":"救火还是追查旧账"}',
                encoding="utf-8",
            )
            (root / "screenplays").mkdir()
            (root / "screenplays/episode-001.md").write_text(
                "【西北拌面王后厨·日·内】\n马小勺把钥匙压在灶台边。",
                encoding="utf-8",
            )
            artifact = build_episode_artifact(root, "episode-001")
        self.assertIn("# 分集编号\nepisode-001", artifact)
        self.assertIn("# 关联角色\n马小勺", artifact)
        self.assertIn("# 关联场景\n西北拌面王后厨", artifact)
        self.assertIn("## 默认下一分集编号\nepisode-002", artifact)


if __name__ == "__main__":
    unittest.main()
