#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
MODULE_PATH = PIPELINE / "versions/0.02/episode-script-validator-biz/scripts/pipeline_guard.py"
SPEC = importlib.util.spec_from_file_location("pipeline_guard_v002", MODULE_PATH)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class PipelineGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "pipeline-state.json"
        guard.init_state(self.state)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_cannot_issue_later_stage_before_previous_acceptance(self) -> None:
        with self.assertRaises(guard.PipelineError):
            guard.issue_ticket(self.state, "writing", self.root / "writing-ticket.json")
        with self.assertRaises(guard.PipelineError):
            guard.issue_ticket(self.state, "validation", self.root / "validation-ticket.json")

    def test_ticket_is_single_stage_and_single_claim(self) -> None:
        ticket = self.root / "planning-ticket.json"
        guard.issue_ticket(self.state, "planning", ticket)
        guard.claim_ticket(self.state, "planning", ticket)
        with self.assertRaises(guard.PipelineError):
            guard.claim_ticket(self.state, "planning", ticket)
        with self.assertRaises(guard.PipelineError):
            guard.require_ticket(guard.require_state(self.state), "writing", ticket)

    def test_structure_only_candidate_cannot_receive_projection_authorization(self) -> None:
        state = guard.require_state(self.state)
        state["status"] = "writing_accepted"
        state["accepted_handoffs"] = {
            "planning": {"path": "planning-handoff.json", "sha256": "1" * 64},
            "writing": {"path": "writing-handoff.json", "sha256": "2" * 64},
        }
        guard.atomic_write(self.state, state)
        ticket = self.root / "validation-ticket.json"
        guard.issue_ticket(self.state, "validation", ticket)
        guard.claim_ticket(self.state, "validation", ticket)
        for name in ("episode-business.json", "completion-receipt.json", "episode-handoff.json"):
            (self.root / name).write_text(json.dumps({"structure": "pass"}), encoding="utf-8")
        with self.assertRaises(guard.PipelineError):
            guard.authorize_projection(
                self.root,
                self.state,
                ticket,
                self.root / "episode-business.json",
                self.root / "completion-receipt.json",
                self.root / "episode-handoff.json",
                self.root / "projection-authorization.json",
                1,
                1,
                0,
            )
        self.assertFalse((self.root / "projection-authorization.json").exists())
        self.assertEqual(guard.require_state(self.state)["status"], "validation_running")

    def test_projection_verification_detects_changed_business_output(self) -> None:
        business = self.root / "episode-business.json"
        receipt = self.root / "completion-receipt.json"
        handoff = self.root / "episode-handoff.json"
        for path in (business, receipt, handoff):
            path.write_text("{}\n", encoding="utf-8")
        state = guard.require_state(self.state)
        state["status"] = "deliverable_accepted"
        state["accepted_handoffs"] = {
            "planning": {"path": "planning-handoff.json", "sha256": "1" * 64},
            "writing": {"path": "writing-handoff.json", "sha256": "2" * 64},
        }
        auth = self.root / "projection-authorization.json"
        payload = {
            "contract_version": guard.AUTH_VERSION,
            "run_id": state["run_id"],
            "status": "DELIVERABLE_ACCEPTED",
            "artifacts": {
                "episode-business.json": guard.sha256(business),
                "completion-receipt.json": guard.sha256(receipt),
                "episode-handoff.json": guard.sha256(handoff),
                "planning-handoff.json": "1" * 64,
                "writing-handoff.json": "2" * 64,
            },
        }
        guard.atomic_write(auth, payload)
        state["projection_authorization"] = {"path": str(auth), "sha256": guard.sha256(auth)}
        guard.atomic_write(self.state, state)
        guard.verify_projection(self.state, auth, business, receipt, handoff)
        business.write_text('{"changed": true}\n', encoding="utf-8")
        with self.assertRaises(guard.PipelineError):
            guard.verify_projection(self.state, auth, business, receipt, handoff)


if __name__ == "__main__":
    unittest.main()
