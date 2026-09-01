import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "business-skill-track/episode-skill-split/versions/0.08"
    / "episode-route-planner-biz/scripts/planning_gate.py"
)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("route_planner_008_count_gate", MODULE_PATH)
planning_gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(planning_gate)
ROUTE_SPEC = importlib.util.spec_from_file_location(
    "route_planner_008_route_contract", MODULE_PATH.parent / "route_contract.py"
)
route_contract = importlib.util.module_from_spec(ROUTE_SPEC)
assert ROUTE_SPEC.loader is not None
ROUTE_SPEC.loader.exec_module(route_contract)
SHAPE_SPEC = importlib.util.spec_from_file_location(
    "route_planner_008_shape_lock", MODULE_PATH.parent / "shape_lock.py"
)
shape_lock = importlib.util.module_from_spec(SHAPE_SPEC)
assert SHAPE_SPEC.loader is not None
SHAPE_SPEC.loader.exec_module(shape_lock)
WORKFLOW_SPEC = importlib.util.spec_from_file_location(
    "route_planner_008_workflow_state", MODULE_PATH.parent / "workflow_state.py"
)
workflow_state = importlib.util.module_from_spec(WORKFLOW_SPEC)
assert WORKFLOW_SPEC.loader is not None
WORKFLOW_SPEC.loader.exec_module(workflow_state)
TOPOLOGY_SPEC = importlib.util.spec_from_file_location(
    "route_planner_008_topology_selection", MODULE_PATH.parent / "topology_selection.py"
)
topology_selection = importlib.util.module_from_spec(TOPOLOGY_SPEC)
assert TOPOLOGY_SPEC.loader is not None
TOPOLOGY_SPEC.loader.exec_module(topology_selection)


def candidate(
    ending_types: tuple[str, ...] = ("main", "expected"),
    narrative_count: int = 4,
) -> dict:
    def node(*, choice: bool, ending: bool, ending_type: str | None = None) -> dict:
        return {
            "互动节点": {"是否为分支节点": choice},
            "是否结局": ending,
            "ending_type": ending_type,
        }

    return {
        "nodes": [
            node(choice=True, ending=False),
            *(node(choice=False, ending=False) for _ in range(narrative_count - len(ending_types))),
            *(node(choice=False, ending=True, ending_type=value) for value in ending_types),
        ]
    }


def intent(**overrides: int | None) -> dict:
    counts = {
        "episode_count": 4,
        "choice_node_count": 1,
        "ending_count": 2,
    }
    counts.update(overrides)
    return {"hard_counts": counts}


class RoutePlanner008CountGateTests(unittest.TestCase):
    def test_same_graph_with_different_prose_has_same_early_fingerprint(self) -> None:
        def route(first_title: str) -> dict:
            return {
                "nodes": [
                    {"node_id": "episode-001", "分集标题": first_title, "是否结局": False, "ending_type": None, "互动节点": {"是否为分支节点": True}, "后续节点编号列表": ["episode-002", "episode-003"]},
                    {"node_id": "episode-002", "分集标题": "结局甲", "是否结局": True, "ending_type": "main", "互动节点": {"是否为分支节点": False}, "后续节点编号列表": []},
                    {"node_id": "episode-003", "分集标题": "结局乙", "是否结局": True, "ending_type": "expected", "互动节点": {"是否为分支节点": False}, "后续节点编号列表": []},
                ]
            }

        self.assertEqual(
            topology_selection.topology_fingerprint(route("选择留下")),
            topology_selection.topology_fingerprint(route("换一种说法")),
        )

    def test_formal_route_does_not_expose_skill_release_version(self) -> None:
        self.assertFalse((MODULE_PATH.parents[1] / "reference-manifest.json").exists())
        self.assertNotIn("skill_version", route_contract.ROOT_FIELDS)
        self.assertFalse(hasattr(route_contract, "SKILL_VERSION"))

    def test_matching_frozen_counts_pass(self) -> None:
        errors: list[str] = []
        planning_gate.validate_user_counts(candidate(), intent(), errors)
        self.assertEqual(errors, [])

    def test_choice_node_does_not_consume_a_narrative_node_slot(self) -> None:
        self.assertEqual(
            planning_gate.route_counts(candidate()),
            {"episode_count": 4, "choice_node_count": 1, "ending_count": 2},
        )

    def test_each_non_null_count_is_checked_against_formal_candidate(self) -> None:
        errors: list[str] = []
        planning_gate.validate_user_counts(candidate(), intent(ending_count=3), errors)
        self.assertEqual(errors, ["用户硬数量未满足：ending_count要求3，实际2"])

    def test_null_count_is_not_inferred(self) -> None:
        errors: list[str] = []
        planning_gate.validate_user_counts(candidate(), intent(ending_count=None), errors)
        self.assertEqual(errors, [])

    def test_explicit_two_endings_override_default_four_type_policy(self) -> None:
        errors: list[str] = []
        planning_gate.validate_ending_policy(candidate(), intent(ending_count=2), errors)
        self.assertEqual(errors, [])

    def test_any_explicit_ending_count_disables_default_four_type_policy(self) -> None:
        errors: list[str] = []
        planning_gate.validate_ending_policy(candidate(), intent(episode_count=4, ending_count=5), errors)
        self.assertEqual(errors, [])

    def test_unspecified_ending_count_keeps_default_four_type_policy(self) -> None:
        errors: list[str] = []
        planning_gate.validate_ending_policy(candidate(), intent(ending_count=None), errors)
        self.assertIn("默认四类结局不完整", errors[0])

    def test_unrestricted_route_with_four_types_passes_default_policy(self) -> None:
        errors: list[str] = []
        route = candidate(("main", "expected", "failure", "small"))
        planning_gate.validate_ending_policy(route, intent(episode_count=5, ending_count=None), errors)
        self.assertEqual(errors, [])

    def test_exact_shape_workflow_has_one_draft_and_no_content_reviews(self) -> None:
        outputs = {name for name, _ in workflow_state.EXACT_FILE_STEPS}
        self.assertIn("topology-draft-1.json", outputs)
        self.assertNotIn("topology-draft-2.json", outputs)
        self.assertNotIn("topology-comparison-packet.json", outputs)
        self.assertNotIn("topology-review-a.json", outputs)
        self.assertNotIn("topology-review-b.json", outputs)

    def test_exact_shape_lock_checks_decision_connections_independent_of_story_cards(self) -> None:
        route = {
            "nodes": [
                {"node_id": "episode-001", "是否结局": False, "互动节点": {"是否为分支节点": False}, "后续节点编号列表": ["episode-002"]},
                {"node_id": "episode-002", "是否结局": False, "互动节点": {"是否为分支节点": True}, "后续节点编号列表": ["episode-003", "episode-004"]},
                {"node_id": "episode-003", "是否结局": True, "ending_type": "main", "互动节点": {"是否为分支节点": False}, "后续节点编号列表": []},
                {"node_id": "episode-004", "是否结局": False, "互动节点": {"是否为分支节点": False}, "后续节点编号列表": ["episode-005"]},
                {"node_id": "episode-005", "是否结局": True, "ending_type": "expected", "互动节点": {"是否为分支节点": False}, "后续节点编号列表": []},
            ]
        }
        lock = {
            "nodes": [
                {"lock_id": "start", "kind": "start", "ending_type": None},
                {"lock_id": "choice", "kind": "choice", "ending_type": None},
                {"lock_id": "ending-a", "kind": "ending", "ending_type": "main"},
                {"lock_id": "ending-b", "kind": "ending", "ending_type": "expected"},
            ],
            "edges": [
                {"source": "start", "target": "choice"},
                {"source": "choice", "target": "ending-a"},
                {"source": "choice", "target": "ending-b"},
            ],
        }
        self.assertTrue(shape_lock.route_satisfies_exact_lock(route, lock))
        route["nodes"][1]["后续节点编号列表"] = ["episode-003"]
        self.assertFalse(shape_lock.route_satisfies_exact_lock(route, lock))


if __name__ == "__main__":
    unittest.main()
