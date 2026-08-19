import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from action_contracts import GENERATIVE_ACTIONS, REVIEW_ACTIONS, TRANSITIONS
from validate_compact_draft import validate as validate_compact_draft


class WritingChainTests(unittest.TestCase):
    def test_compact_draft_chain_has_one_full_writer(self):
        self.assertEqual(GENERATIVE_ACTIONS, {"WRITE_COMPACT_DRAFT", "ENHANCE"})
        self.assertEqual(REVIEW_ACTIONS, set())
        self.assertEqual(
            " -> ".join(next(iter(step)) for step in TRANSITIONS.values()),
            "ADAPT -> WRITE_COMPACT_DRAFT -> VALIDATE_COMPACT_DRAFT -> ENHANCE -> VALIDATE_STRUCTURE -> ACCEPT_EPISODE",
        )

    def test_old_child_and_full_draft_modules_are_absent(self):
        for relative in (
            "scripts/commit_child_result.py",
            "scripts/validate_screenwriter_draft.py",
            "references/vimax-screenwriter.md",
            "references/topology-independent-review.md",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

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

    def test_compact_draft_requires_visible_state_change(self):
        base = """【主控室·暴雨夜·内】
林砚接上应急电源，机械表指向四十五分钟。他把撤离照明和穹顶供电分到两个接口，周岚压住总闸。
周岚：先让求救设备工作，别把电全送上去。
终端噪声中响起导师的声音，要求林砚立刻接满穹顶输出。林砚伸手，周岚把检查表塞进闸刀下阻住他。
林砚：他知道刚才那道闪电落在哪里，这不是旧录音。
林砚改接短波求救，绿色指示灯亮起，机械表降到三十八分钟；导师的声音随即中断。林砚停手，看向重新变成噪声的终端。
周岚拔出检查表，但仍守着总闸。两人确认供电动作已经改变现场状态，却还不能证明声音来自现在。
林砚把穹顶电缆握在手里，没有接入。窗外又一次闪电照亮穹顶，终端保持沉默，选择压力留在两人之间。
雨水沿主控室门缝渗进来，碰到撤离照明电缆。周岚把电缆拖离水迹，林砚扶住分配器；这段耽搁让两人都看见剩余电量正在被现实动作消耗。终端没有再给出可供判断的新回应，他们只能依据眼前设备和彼此的行动决定下一步。
"""
        self.assertEqual(validate_compact_draft(base), [])
        frozen = base.replace("绿色指示灯亮起，机械表降到三十八分钟；", "机械表仍停在四十五分钟；").replace("重新变成噪声", "始终是噪声").replace("响起导师的声音", "一直有导师的声音")
        self.assertTrue(any("状态变化" in issue for issue in validate_compact_draft(frozen)))


if __name__ == "__main__":
    unittest.main()
