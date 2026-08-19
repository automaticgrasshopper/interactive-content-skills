import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_canvas_snapshot import VERSION, validate

REQUEST = "修改第2集".encode()


def node(ref, number, predecessors=None, successors=None, name=None, node_type="video"):
    prefix = "episode" if node_type == "video" else "choice"
    label = f"第{number}集" if node_type == "video" else f"选择{number}"
    return {
        "node_ref": ref,
        "node_type": node_type,
        "display_number": number,
        "display_id": f"{prefix}-{number:03d}",
        "display_name": name or label,
        "predecessors": predecessors or [],
        "successors": successors or [],
        "choices": [],
    }


def snapshot(nodes, operation="update", selections=None):
    return {
        "contract_version": VERSION,
        "scope": "full-graph",
        "user_request_sha256": hashlib.sha256(REQUEST).hexdigest(),
        "node_count": len(nodes),
        "operation": operation,
        "selections": selections or [],
        "nodes": nodes,
    }


class StableCanvasIdentityTests(unittest.TestCase):
    def test_insertion_reorders_display_but_keeps_identity(self):
        nodes = [
            node("stable-a", 1, successors=["stable-new"]),
            node("stable-new", 2, predecessors=["stable-a"], successors=["stable-b"]),
            node("stable-b", 3, predecessors=["stable-new"], successors=["stable-c"]),
            node("stable-c", 4, predecessors=["stable-b"]),
        ]
        issues, receipt = validate(snapshot(
            nodes,
            selections=[{"selector": "第3集", "purpose": "target", "node_ref": "stable-b"}],
        ), REQUEST)
        self.assertEqual(issues, [])
        self.assertEqual(receipt["locked_node_ref"], "stable-b")
        self.assertEqual(receipt["resolution_audit"][0]["display_number"], 3)

    def test_deletion_uses_new_position_not_deleted_position(self):
        nodes = [
            node("stable-a", 1, successors=["stable-c"]),
            node("stable-c", 2, predecessors=["stable-a"]),
        ]
        issues, receipt = validate(snapshot(
            nodes,
            selections=[{"selector": "第2集", "purpose": "target", "node_ref": "stable-c"}],
        ), REQUEST)
        self.assertEqual(issues, [])
        self.assertEqual(receipt["locked_node_ref"], "stable-c")

    def test_node_ref_suffix_never_overrides_latest_display(self):
        nodes = [
            node("node-001", 1, successors=["node-999"]),
            node("node-999", 2, predecessors=["node-001"], successors=["node-003"]),
            node("node-003", 3, predecessors=["node-999"], successors=["node-002"]),
            node("node-002", 4, predecessors=["node-003"]),
        ]
        data = snapshot(nodes, selections=[
            {"selector": "第2集", "purpose": "target", "node_ref": "node-002"},
        ])
        issues, _ = validate(data, REQUEST)
        self.assertTrue(any("定位声明与本轮display字段不一致" in issue for issue in issues))
        data["selections"][0]["node_ref"] = "node-999"
        issues, receipt = validate(data, REQUEST)
        self.assertEqual(issues, [])
        self.assertEqual(receipt["locked_node_ref"], "node-999")

    def test_move_and_reconnect_lock_only_current_refs(self):
        nodes = [
            node("alpha", 1, successors=["gamma"]),
            node("gamma", 2, predecessors=["alpha"], successors=["beta"]),
            node("beta", 3, predecessors=["gamma"]),
        ]
        move = snapshot(nodes, operation="move", selections=[
            {"selector": "第3集", "purpose": "target", "node_ref": "beta"},
            {"selector": "episode-001", "purpose": "anchor", "node_ref": "alpha"},
        ])
        issues, receipt = validate(move, REQUEST)
        self.assertEqual(issues, [])
        self.assertEqual(receipt["locked_node_ref"], "beta")
        self.assertEqual(receipt["locked_anchor_node_refs"], ["alpha"])
        reconnect = snapshot(nodes, operation="reconnect", selections=[
            {"selector": "第1集", "purpose": "anchor", "node_ref": "alpha"},
            {"selector": "第3集", "purpose": "anchor", "node_ref": "beta"},
        ])
        issues, receipt = validate(reconnect, REQUEST)
        self.assertEqual(issues, [])
        self.assertIsNone(receipt["locked_node_ref"])
        self.assertEqual(receipt["locked_anchor_node_refs"], ["alpha", "beta"])

    def test_display_numbers_must_be_current_contiguous_order(self):
        nodes = [node("alpha", 1, successors=["beta"]), node("beta", 3, predecessors=["alpha"])]
        issues, _ = validate(snapshot(nodes, selections=[
            {"selector": "第3集", "purpose": "target", "node_ref": "beta"},
        ]), REQUEST)
        self.assertTrue(any("video display_number必须从1连续排列" in issue for issue in issues))

    def test_video_and_choice_display_numbers_are_independent(self):
        nodes = [
            node("opaque-a", 1, successors=["opaque-choice"]),
            node("opaque-choice", 1, predecessors=["opaque-a"], successors=["opaque-b"], node_type="choice"),
            node("opaque-b", 2, predecessors=["opaque-choice"]),
        ]
        issues, receipt = validate(snapshot(nodes, selections=[
            {"selector": "第2集", "purpose": "target", "node_ref": "opaque-b"},
        ]), REQUEST)
        self.assertEqual(issues, [])
        self.assertEqual(receipt["locked_node_ref"], "opaque-b")

    def test_unresolved_target_requires_route_refresh_before_user_response(self):
        nodes = [node("opaque-a", 1), node("opaque-b", 2)]
        issues, receipt = validate(snapshot(nodes, selections=[
            {"selector": "第3集", "purpose": "target", "node_ref": None},
        ]), REQUEST)
        self.assertIsNone(receipt)
        self.assertTrue(any(issue.startswith("REFRESH_ROUTE_REQUIRED") for issue in issues))

    def test_current_request_can_resolve_null_ref_without_guessing_identity(self):
        nodes = [node("opaque-a", 1), node("opaque-new", 2)]
        issues, receipt = validate(snapshot(nodes, selections=[
            {"selector": "第2集", "purpose": "target", "node_ref": None},
        ]), REQUEST)
        self.assertEqual(issues, [])
        self.assertEqual(receipt["locked_node_ref"], "opaque-new")
        self.assertNotIn("project_revision", receipt)

    def test_engineering_identity_fields_are_not_business_output_fields(self):
        text = (ROOT / "references/business-interface.md").read_text(encoding="utf-8")
        output_tree = text.split("## Skill 输出字段", 1)[1].split("## 输出约束", 1)[0]
        for field in ("node_ref", "display_number", "display_id", "display_name"):
            self.assertNotIn(field, output_tree)


if __name__ == "__main__":
    unittest.main()
