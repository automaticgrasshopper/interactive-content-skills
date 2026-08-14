#!/usr/bin/env python3
"""Enforce ordered, isolated stage execution and authorize formal projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "nextplay.episode-split-run.v1"
AUTH_VERSION = "nextplay.episode-projection-authorization.v1"
STAGES = ("planning", "writing", "validation")
PREVIOUS_STATUS = {
    "planning": "initialized",
    "writing": "planning_accepted",
    "validation": "writing_accepted",
}


class PipelineError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"无法读取合法JSON：{path}") from exc
    if not isinstance(data, dict):
        raise PipelineError(f"JSON顶层不是对象：{path}")
    return data


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def require_state(path: Path) -> dict[str, Any]:
    state = load_json(path)
    if state.get("contract_version") != CONTRACT_VERSION:
        raise PipelineError("流水线状态合同不匹配")
    if not isinstance(state.get("run_id"), str) or not state["run_id"]:
        raise PipelineError("流水线缺少run_id")
    return state


def ticket_digest(ticket: dict[str, Any]) -> str:
    canonical = json.dumps(ticket, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def require_ticket(state: dict[str, Any], stage: str, ticket_path: Path) -> dict[str, Any]:
    ticket = load_json(ticket_path)
    if ticket.get("contract_version") != CONTRACT_VERSION:
        raise PipelineError("阶段票据合同不匹配")
    if ticket.get("run_id") != state.get("run_id") or ticket.get("stage") != stage:
        raise PipelineError("阶段票据不属于当前运行或当前阶段")
    expected = (state.get("tickets") or {}).get(stage)
    if expected != ticket_digest(ticket):
        raise PipelineError("阶段票据未登记或已被替换")
    return ticket


def init_state(state_path: Path) -> None:
    if state_path.exists():
        raise PipelineError("流水线状态已存在；新运行必须使用新的缓存目录")
    atomic_write(
        state_path,
        {
            "contract_version": CONTRACT_VERSION,
            "run_id": str(uuid.uuid4()),
            "status": "initialized",
            "tickets": {},
            "accepted_handoffs": {},
        },
    )
    print("PIPELINE_INITIALIZED")


def issue_ticket(state_path: Path, stage: str, output: Path) -> None:
    state = require_state(state_path)
    expected = PREVIOUS_STATUS[stage]
    if state.get("status") != expected:
        raise PipelineError(f"阶段顺序错误：{stage}要求状态{expected}")
    ticket = {
        "contract_version": CONTRACT_VERSION,
        "run_id": state["run_id"],
        "stage": stage,
        "worker_marker": f"STAGE_WORKER:{stage}",
        "nonce": secrets.token_hex(24),
    }
    state.setdefault("tickets", {})[stage] = ticket_digest(ticket)
    state["status"] = f"{stage}_issued"
    atomic_write(output, ticket)
    atomic_write(state_path, state)
    print(f"{stage.upper()}_TICKET_ISSUED")


def claim_ticket(state_path: Path, stage: str, ticket_path: Path) -> None:
    state = require_state(state_path)
    if state.get("status") != f"{stage}_issued":
        raise PipelineError("阶段未被调度或已被其他执行领取")
    ticket = require_ticket(state, stage, ticket_path)
    state["status"] = f"{stage}_running"
    state["active_worker"] = {
        "stage": stage,
        "ticket_sha256": ticket_digest(ticket),
    }
    atomic_write(state_path, state)
    print(f"{stage.upper()}_WORKER_CLAIMED")


def accept_handoff(state_path: Path, stage: str, ticket_path: Path, handoff_path: Path) -> None:
    if stage not in ("planning", "writing"):
        raise PipelineError("只有规划和写作阶段使用交接放行")
    state = require_state(state_path)
    if state.get("status") != f"{stage}_running":
        raise PipelineError("当前阶段未处于独立执行中")
    require_ticket(state, stage, ticket_path)
    handoff = load_json(handoff_path)
    expected_status = "PLANNING_ACCEPTED" if stage == "planning" else "WRITING_ACCEPTED"
    if handoff.get("stage") != stage or handoff.get("status") != expected_status:
        raise PipelineError("交接文件未取得对应阶段放行")
    if handoff.get("pipeline_run_id") != state.get("run_id"):
        raise PipelineError("交接文件未绑定当前流水线运行")
    handoff_script = Path(__file__).with_name("stage_handoff.py")
    if stage == "planning":
        command = [
            sys.executable, str(handoff_script), "planning-verify", str(state_path.parent),
            "--pipeline-state", str(state_path), "--planning-handoff", str(handoff_path),
        ]
        expected_line = "PLANNING_HANDOFF_PASS"
    else:
        planning_path = Path(state["accepted_handoffs"]["planning"]["path"])
        command = [
            sys.executable, str(handoff_script), "writing-verify", str(state_path.parent),
            "--pipeline-state", str(state_path), "--planning-handoff", str(planning_path),
            "--writing-handoff", str(handoff_path),
        ]
        expected_line = "WRITING_HANDOFF_PASS"
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or expected_line not in result.stdout.splitlines():
        raise PipelineError(f"阶段交接未通过确定性验证：{stage}")
    state["status"] = f"{stage}_accepted"
    state["active_worker"] = None
    state.setdefault("accepted_handoffs", {})[stage] = {
        "path": str(handoff_path.resolve()),
        "sha256": sha256(handoff_path),
    }
    atomic_write(state_path, state)
    print(f"{stage.upper()}_STAGE_ACCEPTED")


def authorize_projection(
    root: Path,
    state_path: Path,
    ticket_path: Path,
    business: Path,
    receipt: Path,
    handoff: Path,
    output: Path,
    endings: int,
    formal: int | None,
    failure: int | None,
) -> None:
    state = require_state(state_path)
    if state.get("status") != "validation_running":
        raise PipelineError("校验阶段未在独立执行中")
    require_ticket(state, "validation", ticket_path)
    command = [
        sys.executable,
        str(Path(__file__).with_name("verify_deliverable.py")),
        str(root.resolve()),
        str(business.resolve()),
        str(receipt.resolve()),
        str(handoff.resolve()),
        "--expected-endings",
        str(endings),
    ]
    if formal is not None:
        command.extend(["--expected-formal", str(formal)])
    if failure is not None:
        command.extend(["--expected-failure", str(failure)])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not lines or lines[0] != "DELIVERABLE_ACCEPTED":
        raise PipelineError("正式交付未取得DELIVERABLE_ACCEPTED")
    authorization = {
        "contract_version": AUTH_VERSION,
        "run_id": state["run_id"],
        "status": "DELIVERABLE_ACCEPTED",
        "artifacts": {
            "episode-business.json": sha256(business),
            "completion-receipt.json": sha256(receipt),
            "episode-handoff.json": sha256(handoff),
            "planning-handoff.json": state["accepted_handoffs"]["planning"]["sha256"],
            "writing-handoff.json": state["accepted_handoffs"]["writing"]["sha256"],
        },
    }
    atomic_write(output, authorization)
    state["status"] = "deliverable_accepted"
    state["active_worker"] = None
    state["projection_authorization"] = {
        "path": str(output.resolve()),
        "sha256": sha256(output),
    }
    atomic_write(state_path, state)
    print(result.stdout.strip())
    print("PROJECTION_AUTHORIZATION_CREATED")


def verify_projection(
    state_path: Path,
    authorization_path: Path,
    business: Path,
    receipt: Path,
    handoff: Path,
) -> None:
    state = require_state(state_path)
    if state.get("status") != "deliverable_accepted":
        raise PipelineError("流水线尚未取得正式交付放行")
    authorization = load_json(authorization_path)
    if authorization.get("contract_version") != AUTH_VERSION:
        raise PipelineError("投影授权合同不匹配")
    if authorization.get("run_id") != state.get("run_id"):
        raise PipelineError("投影授权不属于当前运行")
    if authorization.get("status") != "DELIVERABLE_ACCEPTED":
        raise PipelineError("投影授权状态未放行")
    expected = {
        "episode-business.json": sha256(business),
        "completion-receipt.json": sha256(receipt),
        "episode-handoff.json": sha256(handoff),
        "planning-handoff.json": state["accepted_handoffs"]["planning"]["sha256"],
        "writing-handoff.json": state["accepted_handoffs"]["writing"]["sha256"],
    }
    if authorization.get("artifacts") != expected:
        raise PipelineError("正式交付或阶段交接在授权后发生变化")
    if (state.get("projection_authorization") or {}).get("sha256") != sha256(authorization_path):
        raise PipelineError("投影授权未登记到当前流水线")
    print("PROJECTION_AUTHORIZED")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--state", type=Path, required=True)
    issue = sub.add_parser("issue")
    issue.add_argument("stage", choices=STAGES)
    issue.add_argument("--state", type=Path, required=True)
    issue.add_argument("--output", type=Path, required=True)
    claim = sub.add_parser("claim")
    claim.add_argument("stage", choices=STAGES)
    claim.add_argument("--state", type=Path, required=True)
    claim.add_argument("--ticket", type=Path, required=True)
    accept = sub.add_parser("accept")
    accept.add_argument("stage", choices=("planning", "writing"))
    accept.add_argument("--state", type=Path, required=True)
    accept.add_argument("--ticket", type=Path, required=True)
    accept.add_argument("--handoff", type=Path, required=True)
    authorize = sub.add_parser("authorize")
    authorize.add_argument("root", type=Path)
    authorize.add_argument("business", type=Path)
    authorize.add_argument("receipt", type=Path)
    authorize.add_argument("handoff", type=Path)
    authorize.add_argument("--state", type=Path, required=True)
    authorize.add_argument("--ticket", type=Path, required=True)
    authorize.add_argument("--output", type=Path, required=True)
    authorize.add_argument("--expected-endings", type=int, required=True)
    authorize.add_argument("--expected-formal", type=int)
    authorize.add_argument("--expected-failure", type=int)
    verify = sub.add_parser("projection-verify")
    verify.add_argument("business", type=Path)
    verify.add_argument("receipt", type=Path)
    verify.add_argument("handoff", type=Path)
    verify.add_argument("--state", type=Path, required=True)
    verify.add_argument("--authorization", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            init_state(args.state.resolve())
        elif args.command == "issue":
            issue_ticket(args.state.resolve(), args.stage, args.output.resolve())
        elif args.command == "claim":
            claim_ticket(args.state.resolve(), args.stage, args.ticket.resolve())
        elif args.command == "accept":
            accept_handoff(args.state.resolve(), args.stage, args.ticket.resolve(), args.handoff.resolve())
        elif args.command == "authorize":
            authorize_projection(
                args.root.resolve(), args.state.resolve(), args.ticket.resolve(),
                args.business.resolve(), args.receipt.resolve(), args.handoff.resolve(),
                args.output.resolve(), args.expected_endings, args.expected_formal, args.expected_failure,
            )
        else:
            verify_projection(
                args.state.resolve(), args.authorization.resolve(), args.business.resolve(),
                args.receipt.resolve(), args.handoff.resolve(),
            )
    except PipelineError as exc:
        print(f"PIPELINE_REJECTED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
