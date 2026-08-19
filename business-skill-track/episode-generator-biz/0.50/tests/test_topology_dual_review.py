import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import topology_dual_review_gate as gate


class TopologyDualReviewTests(unittest.TestCase):
    def materials(self, root: Path) -> None:
        for index, name in enumerate(gate.MATERIAL_NAMES, 1):
            (root / name).write_text(
                f"{name} 当前材料包含足够长的第{index}项逐字复检证据。\n",
                encoding="utf-8",
            )

    def passing_review(self, root: Path, review_pass: str) -> dict:
        evidence_name = gate.MATERIAL_NAMES[0]
        quote = "当前材料包含足够长的第1项逐字复检证据"
        return {
            "contract_version": gate.REVIEW_VERSION,
            "packet_sha256": gate.packet_sha256(root),
            "review_pass": review_pass,
            "verdict": "PASS",
            "checks": [
                {
                    "check": name,
                    "passed": True,
                    "explanation": "根据当前封闭材料独立判断该项已经成立。",
                    "evidence": [{"artifact": evidence_name, "quote": quote}],
                }
                for name in gate.REQUIRED_CHECKS
            ],
            "issues": [],
        }

    def test_two_current_serial_pass_receipts_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.materials(root)
            review = self.passing_review(root, "A")
            source = root / "review.json"
            source.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            gate.seal(root, source, "a")
            self.assertTrue(any("回执：b" in item for item in gate.verify(root)))
            review_b = self.passing_review(root, "B")
            source.write_text(json.dumps(review_b, ensure_ascii=False), encoding="utf-8")
            gate.seal(root, source, "b")
            self.assertEqual(gate.verify(root), [])

    def test_any_material_change_invalidates_both_reviews(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.materials(root)
            review = self.passing_review(root, "A")
            source = root / "review.json"
            source.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            gate.seal(root, source, "a")
            source.write_text(json.dumps(self.passing_review(root, "B"), ensure_ascii=False), encoding="utf-8")
            gate.seal(root, source, "b")
            (root / "topology.md").write_text("拓扑已经变化。", encoding="utf-8")
            issues = gate.verify(root)
            self.assertTrue(any("复检a" in item and "未绑定" in item for item in issues))
            self.assertTrue(any("复检b" in item and "未绑定" in item for item in issues))


if __name__ == "__main__":
    unittest.main()
