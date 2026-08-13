import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "episode_quality_gate.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("episode_quality_gate_027", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


BAD_SCRIPT = """【大唐边关·白昼·外】

晨钟落下第三声，唐僧将九环锡杖横在石门锁眼前，先让众人退到水渠外侧。

石门佛印忽明忽暗，攻略上的金线却催他对准门心全力下杖。

唐僧改敲三处承重点，沉重石门轰然滑开，渠沿只崩下一块薄石。

孙悟空捻住自动翻动的书角，以金箍棒轻叩纸背，追听其中多出来的一次回响。

纸页立刻学着棒声连响两次，夹缝里还混进一道刻意压低的喘息。

孙悟空忽然按死书页，指出有人藏在攻略背后偷听取经队。

沙悟净蹲到水渠边量过裂口，把省下的时辰和崩落的薄石一同写进行程账册。

猪八戒伸手想划掉损耗，理由是开门既快又没伤着谁。

沙悟净把笔移开，保住“有损”二字，猪八戒只好背起行李跟队。

唐僧放下拳头，命众人分别守住书页、退路和账册，把决定留在两条真实行动之间。

唐僧：门可以快开，代价也得有人记。
孙悟空：这书里多了一口气，不是咱们四个的。
猪八戒：快路就在眼前，还真要先听山里喊什么？
沙悟净：走快路还是救人，两笔都在这里。
唐僧：先选我们要做的事。"""


GOOD_SCRIPT = """【石门外·白昼·外】

唐僧刚抬起锡杖，孙悟空一把攥住杖头。

孙悟空：师父，先别砸。门后有水声，砸塌了谁也过不去。

猪八戒贴到石门上听了听，忙往后躲。

猪八戒：还真有。那怎么办，总不能在这儿等天黑吧？

唐僧收回锡杖，用杖尾依次敲过门框。敲到右下角时，门缝里的水声突然变闷。

沙悟净：右边是空的。师父，你敲这里，我托住门角。

两人刚一用力，门框便往下掉石屑。孙悟空用金箍棒顶住门梁，冲八戒喊了一声。

孙悟空：别看了，过来搭把手！

猪八戒托住另一边。石门擦着地面慢慢挪开，露出只够一人侧身通过的缝。"""


class StylePreflightTests(unittest.TestCase):
    def test_rejects_summary_cadence_and_meta_language(self):
        issues = MODULE.scene_style_issues(BAD_SCRIPT)
        self.assertTrue(any("工程、拓扑或作者摘要措辞" in issue for issue in issues))
        self.assertTrue(any("场尾集中追加对白" in issue for issue in issues))

    def test_accepts_interleaved_plain_scene(self):
        self.assertEqual(MODULE.scene_style_issues(GOOD_SCRIPT), [])


if __name__ == "__main__":
    unittest.main()
