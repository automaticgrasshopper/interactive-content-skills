import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "business-skill-track" / "episode-generator-biz" / "0.48" / "scripts"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


def stage_two_and_state(root, episode_state, leases):
    stage_two = {"contract_version": "nextplay.episode-stage-two-acceptance.v1", "status": "PASS"}
    write_json(root / "stage-two-acceptance.json", stage_two)
    receipt_hash = hashlib.sha256((root / "stage-two-acceptance.json").read_bytes()).hexdigest()
    write_json(root / "run-state.json", {
        "contract_version": "nextplay.episode-atomic-run.v2",
        "run_id": "test-run",
        "status": "IN_PROGRESS",
        "stage_two_receipt_sha256": receipt_hash,
        "episode_order": ["episode-001"],
        "episodes": {
            "episode-001": {
                "state": episode_state,
                "leases": leases,
                "execution_counts": {},
                "content_failures": {},
                "orchestration_failures": {},
                "outputs": {},
                "reviews": {},
            }
        },
        "ending_plan": {"total": 1, "formal": 1, "failure": 0},
    })


def lease(token):
    return {
        "lease": token,
        "owner": "test",
        "input_hashes": {},
        "input_sha256": f"input-{token}",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "status": "RUNNING",
    }


def child_result(action, status, token, content, findings):
    return {
        "contract_version": "nextplay.episode-child-result.v1",
        "action": action,
        "episode_id": "episode-001",
        "input_sha256": f"input-{token}",
        "status": status,
        "content": content,
        "findings": findings,
    }


def long_script(action_line="甲把门推开，门轴发出一声短响。"):
    return f"""【旧屋·深夜·内】

{action_line}

风从门缝灌进来，桌上的纸张被吹到地上。

甲弯腰捡起纸，看见背面留下的新鲜墨迹。

甲：这里刚刚有人来过。

乙从走廊尽头赶来，先看门锁，再看甲手里的纸。

乙：门锁没有撬痕，他可能有钥匙。

甲把纸放到灯下，墨迹边缘仍在缓慢散开。

甲：不是可能。墨还没干，他就在附近。

楼上传来脚步，两人同时停住，没有立刻追上去。

乙：先封住后门，我守楼梯。

甲点头，把桌边的钥匙串递给乙，自己转向后门。

窗外一道车灯扫过墙面，楼上的脚步突然加快。

甲：他听见我们分开了。别追，先把出口锁住。

乙收回迈出的脚，反手扣住楼梯间铁门。

门后传来撞击，墙灰落在两人肩上，局面从搜索变成围堵。

甲没有去碰铁门，只把掉在地上的纸重新压回桌面。

甲：他在等我们开门。先听他往哪边走。

撞击停了，短暂的安静里，天花板上方传来木板受力的轻响。

乙抬头看向通风口，把刚拿出的钥匙重新攥回掌心。
"""


def formal_episode(script):
    return f"""# 分集编号

episode-001

# 分集标题

旧屋

# 分集剧本

## 单集梗概

甲乙在旧屋发现入侵者并封住出口。

## 完整剧本

{script.strip()}

# 剧本分析

## 本集冲突

两人必须阻止入侵者离开。

## 前置节点编号列表

无

## 后续节点编号列表

无

# 关联角色

甲、乙

# 关联场景

旧屋

# 关联道具

钥匙串

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
"""


class AtomicFlowTests(unittest.TestCase):
    def test_merge_accepts_one_failure_and_one_pass_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = long_script().strip()
            enhanced = root / "enhanced-screenplays" / "episode-001.md"
            enhanced.parent.mkdir(parents=True)
            enhanced.write_text(script + "\n", encoding="utf-8")
            script_hash = hashlib.sha256(script.encode()).hexdigest()
            line = next(i for i, text in enumerate(script.splitlines(), 1) if "门轴发出" in text)
            issue = {
                "issue_id": "issue-1",
                "category": "动作反馈",
                "start_line": line,
                "end_line": line,
                "anchor": "门轴发出一声短响",
                "reason": "动作出现后缺少人物对声音来源的即时判断。",
            }
            drama = root / "drama.json"
            cold = root / "cold.json"
            write_json(drama, {
                "contract_version": "nextplay.episode-review-findings.v1",
                "episode_id": "episode-001",
                "source": "dramatization",
                "script_sha256": script_hash,
                "status": "FAIL",
                "rewrite_required": False,
                "issues": [issue],
            })
            write_json(cold, {
                "episode_id": "episode-001",
                "script_sha256": script_hash,
                "issues": [],
            })
            output = root / "merged-review-findings" / "episode-001.json"
            result = run("review_repair_gate.py", "merge", root, "episode-001", drama, cold, "--output", output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(json.loads(output.read_text(encoding="utf-8"))["issues"]), 1)

    def test_review_failures_commit_findings_and_advance_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stage_two_and_state(root, "REVIEWS_PREPARED", {
                "REVIEW_DRAMA": lease("drama"),
                "REVIEW_COLD_READ": lease("cold"),
            })
            script = long_script()
            path = root / "enhanced-screenplays" / "episode-001.md"
            path.parent.mkdir(parents=True)
            path.write_text(script, encoding="utf-8")
            anchor_line = next(i for i, line in enumerate(script.splitlines(), 1) if "门轴发出" in line)
            issue = {
                "issue_id": "issue-1",
                "category": "动作反馈",
                "start_line": anchor_line,
                "end_line": anchor_line,
                "anchor": "门轴发出一声短响",
                "reason": "动作出现后缺少人物对声音来源的即时判断。",
            }
            for action, token in (("REVIEW_DRAMA", "drama"), ("REVIEW_COLD_READ", "cold")):
                result_path = root / f"{action}.json"
                write_json(result_path, child_result(action, "FAIL", token, '{"rewrite_required": false}', [issue]))
                result = run("commit_child_result.py", root, "episode-001", action, result_path, "--lease", token)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["episodes"]["episode-001"]["state"], "REVIEWS_FAILED")
            self.assertTrue((root / "review-findings" / "episode-001.dramatization.json").is_file())
            self.assertTrue((root / "review-findings" / "episode-001.cold-read.json").is_file())

    def test_repair_commit_updates_both_scripts_and_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stage_two_and_state(root, "FINDINGS_MERGED", {"REPAIR": lease("repair")})
            baseline = long_script()
            repaired = long_script("甲慢慢把门推开，门轴发出一声短响。")
            enhanced = root / "enhanced-screenplays" / "episode-001.md"
            formal = root / "episodes" / "episode-001.md"
            enhanced.parent.mkdir(parents=True)
            formal.parent.mkdir(parents=True)
            enhanced.write_text(baseline, encoding="utf-8")
            formal.write_text(formal_episode(baseline), encoding="utf-8")
            line = next(i for i, text in enumerate(baseline.splitlines(), 1) if "门轴发出" in text)
            write_json(root / "merged-review-findings" / "episode-001.json", {
                "contract_version": "nextplay.episode-merged-findings.v1",
                "episode_id": "episode-001",
                "script_sha256": hashlib.sha256(baseline.strip().encode()).hexdigest(),
                "finding_sha256": ["test"],
                "rewrite_required": False,
                "authorized_ranges": [[line, line]],
                "issues": [{"issue_id": "issue-1"}],
            })
            result_path = root / "repair.json"
            write_json(result_path, child_result("REPAIR", "PASS", "repair", repaired, []))
            result = run("commit_child_result.py", root, "episode-001", "REPAIR", result_path, "--lease", "repair")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["episodes"]["episode-001"]["state"], "REPAIRED")
            self.assertTrue((root / "review-repair-receipts" / "episode-001.json").is_file())
            self.assertIn("甲慢慢把门推开", formal.read_text(encoding="utf-8"))

    def test_rewrite_archives_failed_attempt_and_returns_to_screenwriter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stage_two_and_state(root, "FINDINGS_MERGED", {})
            write_json(root / "merged-review-findings" / "episode-001.json", {"rewrite_required": True})
            draft = root / "screenplay-drafts" / "episode-001.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("old", encoding="utf-8")
            result = run("run_state.py", "rewrite", root, "episode-001", "--reason", "问题覆盖整集，需要重新编剧")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["episodes"]["episode-001"]["state"], "ADAPTED")
            self.assertFalse(draft.exists())
            self.assertTrue(any((root / "rewrite-history" / "episode-001").rglob("rewrite-receipt.json")))


if __name__ == "__main__":
    unittest.main()
