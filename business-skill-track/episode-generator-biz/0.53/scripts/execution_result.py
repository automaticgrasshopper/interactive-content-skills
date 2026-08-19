#!/usr/bin/env python3
"""Shared handled-result protocol for every production CLI in this Skill."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


VERSION = "nextplay.episode-execution-result.v1"
HANDLED_STATUSES = {"ACCEPTED", "IN_PROGRESS", "WAITING_USER", "STOPPED"}


@dataclass(frozen=True)
class HandledOutcome:
    """A normal control outcome, never a process error code."""

    reason_code: str
    action: str
    source_script: str


def not_accepted(script_path: str) -> HandledOutcome:
    name = Path(script_path).name
    return HandledOutcome(
        reason_code="ACTION_NOT_ACCEPTED",
        action=RECOVERY_ACTIONS.get(name, "RECOVER_CURRENT_ACTION"),
        source_script=name,
    )


def refresh_route(script_path: str) -> HandledOutcome:
    return HandledOutcome(
        reason_code="CURRENT_ROUTE_STALE",
        action="REFRESH_CURRENT_ROUTE",
        source_script=Path(script_path).name,
    )

# A failed validator never decides to involve the user.  It points to one
# deterministic internal recovery action; the workflow controller owns routing.
RECOVERY_ACTIONS = {
    "assemble_business_output.py": "REASSEMBLE_DELIVERABLE",
    "build_asset_catalog.py": "REBUILD_ASSET_CATALOG",
    "build_creative_brief.py": "REBUILD_CREATIVE_BRIEF",
    "build_enhancer_input.py": "REBUILD_ENHANCER_INPUT",
    "build_episode_adaptation_source.py": "REBUILD_ADAPTATION",
    "build_episode_writing_input.py": "REBUILD_EPISODE_WRITING_INPUT",
    "complete_story_gate.py": "REWRITE_COMPLETE_STORY",
    "completion_gate.py": "REBUILD_COMPLETION_RECEIPT",
    "decision_fissure_gate.py": "REBUILD_DECISION_FISSURES",
    "episode_acceptance.py": "REBIND_ACCEPTANCE",
    "episode_structure_gate.py": "RERUN_ENHANCE",
    "planning_acceptance.py": "REBUILD_EARLIEST_PLANNING_ARTIFACT",
    "repair_mainline_projection.py": "REBUILD_MAINLINE_DECOMPOSITION",
    "run_state.py": "RECOVER_EPISODE_RUN",
    "story_treatment_gate.py": "REBUILD_STORY_TREATMENT",
    "synopsis_set_gate.py": "REBUILD_SYNOPSIS_SET",
    "topology_dual_review_gate.py": "REVIEW_TOPOLOGY_A",
    "validate_business_output.py": "REASSEMBLE_DELIVERABLE",
    "validate_canvas_snapshot.py": "REFRESH_CURRENT_ROUTE",
    "validate_character_appearances.py": "REWRITE_COMPACT_DRAFT",
    "validate_compact_draft.py": "REWRITE_COMPACT_DRAFT",
    "validate_creative_brief.py": "REBUILD_CREATIVE_BRIEF",
    "validate_emotional_spine.py": "REPROJECT_EMOTIONAL_SPINE",
    "validate_emotional_topology.py": "REPROJECT_EMOTIONAL_SPINE",
    "validate_episode.py": "RERUN_ENHANCE",
    "validate_mainline_emotional_movement.py": "REBUILD_MAINLINE_EMOTIONAL_MOVEMENT",
    "validate_mainline_projection.py": "REBUILD_MAINLINE_DECOMPOSITION",
    "validate_route_duration.py": "REBUILD_MAINLINE_PATH",
    "validate_story_topology.py": "REBUILD_STORY_TREATMENT",
    "validate_topology.py": "REBUILD_TOPOLOGY",
    "validate_topology_revision.py": "REBUILD_TOPOLOGY",
    "validate_user_intent_lock.py": "REBUILD_USER_INTENT_LOCK",
    "verify_deliverable.py": "REASSEMBLE_DELIVERABLE",
    "workflow_state.py": "RECOVER_WORKFLOW_STATE",
}


def result(
    status: str,
    reason_code: str,
    *,
    issues: list[str] | None = None,
    next_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in HANDLED_STATUSES:
        raise ValueError(f"非法执行状态：{status}")
    value: dict[str, Any] = {
        "contract_version": VERSION,
        "status": status,
        "accepted": status == "ACCEPTED",
        "reason_code": reason_code,
        "issues": issues or [],
    }
    if status == "IN_PROGRESS":
        if not isinstance(next_action, dict) or not next_action.get("action"):
            raise ValueError("IN_PROGRESS必须且只能携带一个next_action")
        value["next_action"] = next_action
    elif next_action is not None:
        value["next_action"] = next_action
    return value


def emit(value: dict[str, Any]) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def _cache_root() -> Path | None:
    """Best-effort cache root discovery for persisting a context-cut resume."""

    for raw in sys.argv[1:]:
        if raw.startswith("-"):
            continue
        path = Path(raw)
        if path.is_dir():
            return path.resolve()
    return None


def _write_resume(root: Path, value: dict[str, Any]) -> None:
    target = root / ".execution-state.json"
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _clear_resume(root: Path | None, script_name: str) -> None:
    if root is None:
        return
    target = root / ".execution-state.json"
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        source = (value.get("next_action") or {}).get("source_script")
        if source == script_name:
            target.unlink()
    except FileNotFoundError:
        return
    except (OSError, ValueError, json.JSONDecodeError):
        # A damaged private resume marker must never invalidate a successful
        # business action. workflow_state will ignore or replace it.
        return


def _issues(output: str) -> list[str]:
    values: list[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        for prefix in ("FAIL：", "FAIL:", "FAIL"):
            if line.startswith(prefix):
                line = line[len(prefix):].strip(" ：:")
                break
        if line and line not in values:
            values.append(line)
    return values or ["当前动作未通过；按唯一内部动作自动恢复"]


def run_cli(main: Callable[[], int | HandledOutcome | None], script_path: str) -> int:
    """Turn expected nonzero CLI outcomes into handled, resumable results.

    Unexpected programming defects deliberately escape this boundary and keep a
    nonzero process exit.  Tests call library functions directly and are not
    affected by this production CLI adapter.
    """

    captured = io.StringIO()
    with redirect_stdout(captured):
        code = main()
    output = captured.getvalue()
    name = Path(script_path).name
    root = _cache_root()
    if code in (None, 0):
        _clear_resume(root, name)
        sys.stdout.write(output)
        return 0

    if not isinstance(code, HandledOutcome):
        raise RuntimeError(f"生产CLI返回了未处理的进程码：{name}/{code}")
    action = code.action
    reason = code.reason_code
    value = result(
        "IN_PROGRESS",
        reason,
        issues=_issues(output),
        next_action={
            "action": action,
            "execution_mode": "current_task",
            "source_script": code.source_script,
        },
    )
    if root is not None:
        try:
            _write_resume(root, value)
        except OSError:
            # The structured stdout result still gives the platform an exact
            # continuation even when the cache itself is temporarily unwritable.
            pass
    return emit(value)
